from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from daily_stock.models import DailyStock
from stations.models import Station, StationManager


def _daily_stock_scope_for_user(user):
    if user.role == "admin":
        return (
            DailyStock.objects.filter(station__owner=user),
            Station.objects.filter(owner=user).order_by("name"),
        )
    if user.role == "manager":
        station_manager = (
            StationManager.objects.filter(manager=user).select_related("station").first()
        )
        if not station_manager:
            return None, None
        return (
            DailyStock.objects.filter(station=station_manager.station),
            Station.objects.filter(id=station_manager.station_id),
        )
    return None, None


@login_required
def daily_sales_view(request):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    base_qs, allowed_stations = _daily_stock_scope_for_user(request.user)
    if base_qs is None:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")

    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "date_desc").strip() or "date_desc"

    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    if not date_from_raw:
        date_from = first_of_month
        date_from_raw = date_from.isoformat()
    else:
        date_from = parse_date(date_from_raw)
    if not date_to_raw:
        date_to = today
        date_to_raw = date_to.isoformat()
    else:
        date_to = parse_date(date_to_raw)

    qs = base_qs.select_related("station", "recorded_by").all()

    if request.user.role == "admin" and station_filter:
        qs = qs.filter(station_id=station_filter)

    if date_from:
        qs = qs.filter(stock_date__gte=date_from)
    if date_to:
        qs = qs.filter(stock_date__lte=date_to)

    stats = qs.aggregate(
        total_gasoline=Sum("qty_gasoline"),
        total_diesel=Sum("qty_diesel"),
    )
    total_entries = qs.count()
    total_gasoline = stats["total_gasoline"] or Decimal("0")
    total_diesel = stats["total_diesel"] or Decimal("0")

    sort_map = {
        "date_desc": ("-stock_date", "-id"),
        "date_asc": ("stock_date", "id"),
        "station_asc": ("station__name", "-stock_date"),
        "station_desc": ("-station__name", "-stock_date"),
    }
    ordering = sort_map.get(sort, sort_map["date_desc"])
    qs = qs.order_by(*ordering)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    manager_station = None
    if request.user.role == "manager":
        sm = StationManager.objects.filter(manager=request.user).select_related("station").first()
        if sm:
            manager_station = sm.station

    context = {
        "daily_stocks": page_obj.object_list,
        "page_obj": page_obj,
        "stations": allowed_stations,
        "show_station_filter": request.user.role == "admin",
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "sort": sort,
        "total_entries": total_entries,
        "total_gasoline": total_gasoline,
        "total_diesel": total_diesel,
        "can_create_daily_stock": request.user.role == "manager" and manager_station is not None,
        "manager_station": manager_station,
    }
    return render(request, "daily_stock.html", context)


@login_required
def daily_stock_create_view(request):
    """Création d'une entrée stock journalier (gérant uniquement, 1 insertion par station et par date)."""
    if request.method != "POST":
        return redirect("daily_stock:daily_sales")

    if request.user.role != "manager":
        messages.error(request, "Seul le gérant peut enregistrer une entrée de stock journalier.")
        return redirect("daily_stock:daily_sales")

    station_manager = (
        StationManager.objects.filter(manager=request.user).select_related("station").first()
    )
    if not station_manager:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")

    stock_date_raw = (request.POST.get("stock_date") or "").strip()
    stock_date = parse_date(stock_date_raw) if stock_date_raw else None
    if not stock_date:
        messages.error(request, "La date du stock est obligatoire et doit être valide.")
        return redirect("daily_stock:daily_sales")

    try:
        qty_gasoline = Decimal((request.POST.get("qty_gasoline") or "0").replace(",", ".").strip() or "0")
        qty_diesel = Decimal((request.POST.get("qty_diesel") or "0").replace(",", ".").strip() or "0")
    except (InvalidOperation, ValueError):
        messages.error(request, "Les quantités doivent être numériques.")
        return redirect("daily_stock:daily_sales")

    if qty_gasoline < 0 or qty_diesel < 0:
        messages.error(request, "Les quantités ne peuvent pas être négatives.")
        return redirect("daily_stock:daily_sales")

    notes = (request.POST.get("notes") or "").strip() or None

    try:
        with transaction.atomic():
            if DailyStock.objects.filter(
                station=station_manager.station,
                stock_date=stock_date,
            ).exists():
                messages.error(
                    request,
                    f"Une entrée de stock journalier existe déjà pour le {stock_date.strftime('%d/%m/%Y')} sur cette station.",
                )
                return redirect("daily_stock:daily_sales")

            DailyStock.objects.create(
                station=station_manager.station,
                stock_date=stock_date,
                recorded_by=request.user,
                qty_gasoline=qty_gasoline,
                qty_diesel=qty_diesel,
                notes=notes,
            )
    except IntegrityError:
        messages.error(
            request,
            f"Une entrée existe déjà pour le {stock_date.strftime('%d/%m/%Y')} sur cette station.",
        )
        return redirect("daily_stock:daily_sales")
    except Exception as exc:
        messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
        return redirect("daily_stock:daily_sales")

    messages.success(
        request,
        f"Stock journalier enregistré pour le {stock_date.strftime('%d/%m/%Y')}.",
    )
    return redirect("daily_stock:daily_sales")
