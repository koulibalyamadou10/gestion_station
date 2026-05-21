from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from daily_stock.models import DailyStock
from inventory.models import Inventory
from pumps.views import reverse_bulk_pump_reading_inventory
from sale.models import Sale
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
        "can_delete_inventory": True,
    }
    return render(request, "inventory_content.html", context)


@login_required
def inventory_delete_view(request, pk):
    """Annule une saisie groupée : inverse bulk_pump_reading_view (admin propriétaire)."""
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut supprimer une ligne d'inventaire.")
        return redirect("inventory:stock_livre")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("inventory:stock_livre")

    inventory_row = get_object_or_404(
        Inventory.objects.select_related("station", "reading_batch").prefetch_related(
            "wallet_allocations"
        ),
        pk=pk,
        station__owner=request.user,
    )

    if inventory_row.source != Inventory.SOURCE_BULK_READING:
        messages.error(
            request,
            "Seules les lignes issues d'une saisie groupée de pompes peuvent être annulées ici.",
        )
        return redirect("inventory:stock_livre")

    station_name = inventory_row.station.name
    d_str = (
        inventory_row.reading_date.strftime("%d/%m/%Y")
        if inventory_row.reading_date
        else inventory_row.created_at.strftime("%d/%m/%Y")
    )

    try:
        reverse_bulk_pump_reading_inventory(inventory_row)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("inventory:stock_livre")
    except Exception as exc:
        messages.error(request, f"Erreur lors de la suppression : {exc}")
        return redirect("inventory:stock_livre")

    messages.success(
        request,
        f"Inventaire du {d_str} ({station_name}) annulé : lectures, ventes, wallets et stock station restaurés.",
    )
    return redirect("inventory:stock_livre")


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


def _aggregate_sales_by_date(station_id, min_date, max_date):
    """Ventes (L) par jour entre deux dates incluses."""
    by_date = defaultdict(lambda: (Decimal("0"), Decimal("0")))
    rows = (
        Sale.objects.filter(
            station_id=station_id,
            sale_date__gte=min_date,
            sale_date__lte=max_date,
        )
        .values("sale_date")
        .annotate(g=Sum("qty_gasoline"), d=Sum("qty_diesel"))
    )
    for row in rows:
        by_date[row["sale_date"]] = (
            row["g"] or Decimal("0"),
            row["d"] or Decimal("0"),
        )
    return by_date


def _sum_sales_in_period(by_date, date_from, date_to):
    total_g = Decimal("0")
    total_d = Decimal("0")
    current = date_from
    while current <= date_to:
        g, d = by_date.get(current, (Decimal("0"), Decimal("0")))
        total_g += g
        total_d += d
        current += timedelta(days=1)
    return total_g, total_d


def _sales_period_for_daily_stock(stock_date, previous_stock_date):
    """
    Période de ventes à imputer au relevé gérant du ``stock_date`` (jauge matin).
    - Premier relevé : ventes du jour du relevé uniquement.
    - Sinon : du lendemain du dernier relevé jusqu'au jour du relevé inclus
      (le stock système reflète souvent les index / ventes déjà décomptés).
    """
    if previous_stock_date is None:
        return stock_date, stock_date
    return previous_stock_date + timedelta(days=1), stock_date


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
        ds_list = list(ds_qs)

        previous_stock_date_by_current = {}
        seen_stock_dates = []
        for ds in sorted(ds_list, key=lambda x: x.stock_date):
            previous_stock_date_by_current[ds.stock_date] = (
                seen_stock_dates[-1] if seen_stock_dates else None
            )
            seen_stock_dates.append(ds.stock_date)

        if ds_list:
            min_sale_date = min(ds.stock_date for ds in ds_list)
            max_sale_date = max(ds.stock_date for ds in ds_list)
            sales_by_date = _aggregate_sales_by_date(
                int(station_filter), min_sale_date, max_sale_date
            )
        else:
            sales_by_date = {}

        for ds in ds_list:
            sys_g, sys_d, system_source = _system_stock_for_daily_compare(
                ds.station_id, ds.stock_date
            )
            decl_g = ds.qty_gasoline or Decimal("0")
            decl_d = ds.qty_diesel or Decimal("0")
            prev_stock_date = previous_stock_date_by_current.get(ds.stock_date)
            sales_from, sales_to = _sales_period_for_daily_stock(
                ds.stock_date, prev_stock_date
            )
            sales_g, sales_d = _sum_sales_in_period(sales_by_date, sales_from, sales_to)
            delta_g = decl_g - sys_g
            delta_d = decl_d - sys_d
            # Écart ajusté : le gérant jauge le matin ; le système a souvent déjà déduit les ventes.
            comparison_rows.append(
                {
                    "daily": ds,
                    "system_gasoline": sys_g,
                    "system_diesel": sys_d,
                    "system_source": system_source,
                    "sales_gasoline": sales_g,
                    "sales_diesel": sales_d,
                    "sales_from": sales_from,
                    "sales_to": sales_to,
                    "delta_gasoline": delta_g,
                    "delta_diesel": delta_d,
                    "delta_adjusted_gasoline": delta_g - sales_g,
                    "delta_adjusted_diesel": delta_d - sales_d,
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
