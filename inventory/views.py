from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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

    total_entries = qs.count()
    last_row = qs.order_by("-created_at", "-id").first()
    if last_row:
        total_gasoline = last_row.qty_gasoline or Decimal("0")
        total_diesel = last_row.qty_diesel or Decimal("0")
    else:
        total_gasoline = Decimal("0")
        total_diesel = Decimal("0")

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
    Dernier snapshot cuves (Inventory) dont la date de création est <= as_of_date (inclus).
    Chaque ligne Inventory = niveau essence + gazoil après une opération système (pas une somme).
    """
    last = (
        Inventory.objects.filter(station_id=station_id, created_at__date__lte=as_of_date)
        .order_by("-created_at", "-id")
        .first()
    )
    if not last:
        return Decimal("0"), Decimal("0")
    return (last.qty_gasoline or Decimal("0"), last.qty_diesel or Decimal("0"))


def _system_stock_for_daily_compare(station_id, stock_date):
    """
    Pour une ligne DailyStock à la date ``stock_date`` :
    - priorité : dernière ligne Inventory créée **le même jour calendaire** (ce que le système
      a enregistré ce jour-là pour cette station) ;
    - sinon : dernier état connu jusqu’à cette date (relevé gérant sans mouvement inventaire ce jour).
    Retourne (qty_essence, qty_gazoil, source) avec source parmi same_day | cumulative | none.
    """
    same_day = (
        Inventory.objects.filter(station_id=station_id, created_at__date=stock_date)
        .order_by("-created_at", "-id")
        .first()
    )
    if same_day:
        return (
            same_day.qty_gasoline or Decimal("0"),
            same_day.qty_diesel or Decimal("0"),
            "same_day",
        )
    sys_g, sys_d = _system_stock_from_inventory_cumulative(station_id, stock_date)
    has_row = Inventory.objects.filter(
        station_id=station_id, created_at__date__lte=stock_date
    ).exists()
    return sys_g, sys_d, ("cumulative" if has_row else "none")


@login_required
def compare_receptions_vs_sales_view(request):
    """
    Compare jour à jour : relevé gérant (DailyStock, une ligne / station / jour) vs
    inventaire système (Inventory : dernier enregistrement du même jour, ou dernier état connu).
    """
    if request.user.role not in ("admin", "super_admin"):
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("account:not_access")

    allowed_stations = _allowed_stations_for_compare(request.user)
    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()

    allowed_station_count = allowed_stations.count()
    if allowed_station_count == 1:
        station_filter = str(allowed_stations.first().pk)
    elif station_filter and not allowed_stations.filter(pk=station_filter).exists():
        station_filter = ""

    show_comparison_table = bool(station_filter)

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

    comparison_rows = []
    daily_stock_count = 0
    if show_comparison_table:
        ds_qs = DailyStock.objects.select_related("station", "recorded_by").filter(
            station__in=allowed_stations,
            station_id=station_filter,
        )
        if date_from:
            ds_qs = ds_qs.filter(stock_date__gte=date_from)
        if date_to:
            ds_qs = ds_qs.filter(stock_date__lte=date_to)

        ds_qs = ds_qs.order_by("-stock_date", "-id")
        daily_stock_count = ds_qs.count()

        for ds in ds_qs:
            sys_g, sys_d, system_source = _system_stock_for_daily_compare(
                ds.station_id, ds.stock_date
            )
            # Écart (L) = relevé gérant (DailyStock) − niveau système (Inventory), signé (+ ou −)
            decl_g = ds.qty_gasoline or Decimal("0")
            decl_d = ds.qty_diesel or Decimal("0")
            comparison_rows.append(
                {
                    "daily": ds,
                    "system_gasoline": sys_g,
                    "system_diesel": sys_d,
                    "system_source": system_source,
                    "delta_gasoline": decl_g - sys_g,
                    "delta_diesel": decl_d - sys_d,
                }
            )

    paginator = Paginator(comparison_rows, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "stations": allowed_stations,
        "station_filter": station_filter,
        "allowed_station_count": allowed_station_count,
        "show_comparison_table": show_comparison_table,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "page_obj": page_obj,
        "comparison_rows": page_obj.object_list,
        "daily_stock_count": daily_stock_count,
    }
    return render(request, "compare_inventory_and_daily_stock.html", context)
