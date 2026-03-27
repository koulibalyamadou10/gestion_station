from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from daily_stock.models import DailyStock
from inventory.models import Inventory
from stations.models import Station


@login_required
def inventory_by_delivery_view(request):
    """Liste des lignes d'inventaire (réceptions enregistrées) pour les stations du compte."""
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut accéder à cette page.")
        return redirect("account:not_access")

    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "created_desc").strip() or "created_desc"

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

    allowed_stations = Station.objects.filter(owner=request.user).order_by("name")

    qs = Inventory.objects.select_related("station").filter(station__in=allowed_stations)

    if station_filter:
        qs = qs.filter(station_id=station_filter)

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    stats = qs.aggregate(
        total_gasoline=Sum("qty_gasoline"),
        total_diesel=Sum("qty_diesel"),
    )
    total_gasoline = stats["total_gasoline"] or Decimal("0")
    total_diesel = stats["total_diesel"] or Decimal("0")
    total_entries = qs.count()

    sort_map = {
        "created_desc": ("-created_at", "-id"),
        "created_asc": ("created_at", "id"),
        "station_asc": ("station__name", "-created_at"),
        "station_desc": ("-station__name", "-created_at"),
    }
    qs = qs.order_by(*sort_map.get(sort, sort_map["created_desc"]))

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "inventory_rows": page_obj.object_list,
        "page_obj": page_obj,
        "stations": allowed_stations,
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "sort": sort,
        "total_entries": total_entries,
        "total_gasoline": total_gasoline,
        "total_diesel": total_diesel,
    }
    return render(request, "inventory_content.html", context)


def _allowed_stations_for_compare(user):
    if user.role == "admin":
        return Station.objects.filter(owner=user).order_by("name")
    if user.role == "super_admin":
        return Station.objects.all().order_by("name")
    return Station.objects.none()


def _system_stock_from_inventory_cumulative(station_id, as_of_date):
    """
    Stock théorique dans les cuves à la fin du jour `as_of_date` (inclus).

    Chaque ligne Inventory reflète le niveau des cuves après l’opération (création station,
    livraisons si enregistrées ainsi, ventes pompes). On prend la **dernière** ligne
    jusqu’à cette date (pas une somme des quantités).
    """
    last = (
        Inventory.objects.filter(station_id=station_id, created_at__date__lte=as_of_date)
        .order_by("-created_at", "-id")
        .first()
    )
    if not last:
        return Decimal("0"), Decimal("0")
    return (last.qty_gasoline or Decimal("0"), last.qty_diesel or Decimal("0"))


@login_required
def compare_receptions_vs_sales_view(request):
    """
    Compare le stock déclaré par le gérant (DailyStock) au stock dérivé du dernier
    enregistrement Inventory (niveaux de cuves après chaque opération).
    """
    if request.user.role not in ("admin", "super_admin"):
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("account:not_access")

    allowed_stations = _allowed_stations_for_compare(request.user)
    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()

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

    ds_qs = DailyStock.objects.select_related("station", "recorded_by").filter(
        station__in=allowed_stations
    )
    if station_filter:
        ds_qs = ds_qs.filter(station_id=station_filter)
    if date_from:
        ds_qs = ds_qs.filter(stock_date__gte=date_from)
    if date_to:
        ds_qs = ds_qs.filter(stock_date__lte=date_to)

    ds_qs = ds_qs.order_by("-stock_date", "-id")

    comparison_rows = []
    for ds in ds_qs:
        sys_g, sys_d = _system_stock_from_inventory_cumulative(ds.station_id, ds.stock_date)
        comparison_rows.append(
            {
                "daily": ds,
                "system_gasoline": sys_g,
                "system_diesel": sys_d,
                "delta_gasoline": (ds.qty_gasoline or Decimal("0")) - sys_g,
                "delta_diesel": (ds.qty_diesel or Decimal("0")) - sys_d,
            }
        )

    inv_detail_qs = Inventory.objects.select_related("station").filter(
        station__in=allowed_stations
    )
    if station_filter:
        inv_detail_qs = inv_detail_qs.filter(station_id=station_filter)
    if date_from:
        inv_detail_qs = inv_detail_qs.filter(created_at__date__gte=date_from)
    if date_to:
        inv_detail_qs = inv_detail_qs.filter(created_at__date__lte=date_to)
    inv_detail_qs = inv_detail_qs.order_by("-created_at", "-id")[:50]

    paginator = Paginator(comparison_rows, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "stations": allowed_stations,
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "page_obj": page_obj,
        "comparison_rows": page_obj.object_list,
        "inventory_movements": inv_detail_qs,
        "daily_stock_count": ds_qs.count(),
    }
    return render(request, "compare_inventory_and_daily_stock.html", context)
