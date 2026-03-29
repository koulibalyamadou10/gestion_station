from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from daily_stock.models import DailyStock
from delivery.models import Delivery
from inventory.models import Inventory
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


def _stock_detail_allowed_stations(user):
    if user.role == "admin":
        return Station.objects.filter(owner=user).order_by("name")
    if user.role == "super_admin":
        return Station.objects.all().order_by("name")
    if user.role == "manager":
        sm = StationManager.objects.filter(manager=user).select_related("station").first()
        if sm:
            return Station.objects.filter(pk=sm.station.pk)
    return Station.objects.none()


def _inventory_qty_at_period_start(station_id, date_from, station_fallback):
    """
    Stock cuve au début de la période : dernier inventaire système avec
    ``created_at`` au plus tard le jour ``date_from`` (inclus), sinon stocks cuve sur la station.
    """
    last = (
        Inventory.objects.filter(
            station_id=station_id, created_at__date__lte=date_from
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if last:
        return last.qty_gasoline or Decimal("0"), last.qty_diesel or Decimal("0")
    g = station_fallback.stock_gasoline or Decimal("0")
    d = station_fallback.stock_diesel or Decimal("0")
    return g, d


def _day_daily_stock_sortie(station_id, d):
    """Sorties du jour : quantités enregistrées dans le stock journalier (DailyStock)."""
    ds = (
        DailyStock.objects.filter(station_id=station_id, stock_date=d)
        .only("qty_gasoline", "qty_diesel")
        .first()
    )
    if not ds:
        return Decimal("0"), Decimal("0")
    return ds.qty_gasoline or Decimal("0"), ds.qty_diesel or Decimal("0")


def _day_reception_net_totals(station_id, d):
    g = Decimal("0")
    dz = Decimal("0")
    for deliv in Delivery.objects.filter(
        order_supplier__order__station_id=station_id,
        delivery_date=d,
    ).only(
        "delivered_qty_gasoline",
        "missing_qty_gasoline",
        "delivered_qty_diesel",
        "missing_qty_diesel",
    ):
        dg = deliv.delivered_qty_gasoline or Decimal("0")
        mg = deliv.missing_qty_gasoline or Decimal("0")
        dd = deliv.delivered_qty_diesel or Decimal("0")
        md = deliv.missing_qty_diesel or Decimal("0")
        g += max(dg - mg, Decimal("0"))
        dz += max(dd - md, Decimal("0"))
    return g, dz


def _build_cuve_ledger(station_id, date_from, date_to, station_obj):
    """
    Grand livre cuves : entrées = réceptions (Delivery, net manquants),
    sorties = stock journalier (DailyStock). Ligne initiale = inventaire (Inventory) à date début.
    """
    open_g, open_d = _inventory_qty_at_period_start(station_id, date_from, station_obj)

    def build_one(opening: Decimal, sortie_fn, recv_fn):
        rows = []
        rows.append(
            {
                "date": date_from,
                "label": "Stock départ",
                "entree": opening,
                "sortie": None,
                "stock": opening,
            }
        )
        cur = opening
        d = date_from
        while d <= date_to:
            sortie_jour = sortie_fn(d)
            recv = recv_fn(d)
            if sortie_jour > 0:
                cur = cur - sortie_jour
                rows.append(
                    {
                        "date": d,
                        "label": "Vente",
                        "entree": None,
                        "sortie": sortie_jour,
                        "stock": cur,
                    }
                )
            if recv > 0:
                cur = cur + recv
                rows.append(
                    {
                        "date": d,
                        "label": "Réception",
                        "entree": recv,
                        "sortie": None,
                        "stock": cur,
                    }
                )
            d += timedelta(days=1)
        return rows

    rows_e = build_one(
        open_g,
        lambda day: _day_daily_stock_sortie(station_id, day)[0],
        lambda day: _day_reception_net_totals(station_id, day)[0],
    )
    rows_g = build_one(
        open_d,
        lambda day: _day_daily_stock_sortie(station_id, day)[1],
        lambda day: _day_reception_net_totals(station_id, day)[1],
    )
    return rows_e, rows_g


def _ledger_period_stats(rows):
    total_entree = Decimal("0")
    total_sortie = Decimal("0")
    for row in rows[1:]:
        if row["label"] == "Réception" and row["entree"] is not None:
            total_entree += row["entree"]
        if row["label"] == "Vente" and row["sortie"] is not None:
            total_sortie += row["sortie"]
    stock_fin = rows[-1]["stock"] if rows else Decimal("0")
    return {
        "total_entree": total_entree,
        "total_sortie": total_sortie,
        "stock_fin": stock_fin,
    }


@login_required
def stock_detail_view(request):
    """
    Détail mouvements cuves sur une période : stock départ (Inventory),
    sorties (DailyStock), entrées (Delivery net).
    """
    if request.user.role not in ("admin", "manager", "super_admin"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    stations_qs = _stock_detail_allowed_stations(request.user)
    if not stations_qs.exists():
        messages.error(request, "Aucune station disponible.")
        return redirect("account:dashboard")

    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    station_filter = request.GET.get("station", "").strip()
    product_filter = (request.GET.get("product", "all") or "all").strip().lower()
    if product_filter not in ("all", "essence", "gazoil"):
        product_filter = "all"

    if not date_from_raw:
        date_from = first_of_month
        date_from_raw = date_from.isoformat()
    else:
        date_from = parse_date(date_from_raw) or first_of_month
        date_from_raw = date_from.isoformat()
    if not date_to_raw:
        date_to = today
        date_to_raw = date_to.isoformat()
    else:
        date_to = parse_date(date_to_raw) or today
        date_to_raw = date_to.isoformat()
    if date_from > date_to:
        date_from, date_to = date_to, date_from
        date_from_raw, date_to_raw = date_from.isoformat(), date_to.isoformat()

    show_station_filter = request.user.role in ("admin", "super_admin")
    if stations_qs.count() == 1:
        station_filter = str(stations_qs.first().pk)
    elif station_filter and not stations_qs.filter(pk=station_filter).exists():
        station_filter = ""

    selected_station = None
    rows_essence = []
    rows_gazoil = []
    stats_e = {
        "total_entree": Decimal("0"),
        "total_sortie": Decimal("0"),
        "stock_fin": Decimal("0"),
    }
    stats_g = {
        "total_entree": Decimal("0"),
        "total_sortie": Decimal("0"),
        "stock_fin": Decimal("0"),
    }

    if station_filter:
        selected_station = stations_qs.filter(pk=station_filter).first()
        if selected_station:
            rows_essence, rows_gazoil = _build_cuve_ledger(
                selected_station.pk, date_from, date_to, selected_station
            )
            stats_e = _ledger_period_stats(rows_essence)
            stats_g = _ledger_period_stats(rows_gazoil)

    context = {
        "stations": stations_qs,
        "station_filter": station_filter,
        "selected_station": selected_station,
        "show_station_filter": show_station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "product_filter": product_filter,
        "rows_essence": rows_essence,
        "rows_gazoil": rows_gazoil,
        "stats_e": stats_e,
        "stats_g": stats_g,
    }
    return render(request, "stock_detail.html", context)


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


@login_required
def daily_stock_delete_view(request, pk):
    """Suppression d'une entrée stock journalier — admin (propriétaire de la station) uniquement."""
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut supprimer une entrée de stock journalier.")
        return redirect("daily_stock:daily_sales")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("daily_stock:daily_sales")

    ds = get_object_or_404(
        DailyStock.objects.select_related("station"),
        pk=pk,
        station__owner=request.user,
    )
    station_name = ds.station.name
    d_str = ds.stock_date.strftime("%d/%m/%Y")
    ds.delete()
    messages.success(
        request,
        f"Entrée du {d_str} ({station_name}) supprimée. Le gérant peut en enregistrer une nouvelle.",
    )
    return redirect("daily_stock:daily_sales")
