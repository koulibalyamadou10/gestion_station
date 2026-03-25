from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from delivery.models import Delivery
from sale.models import Sale
from stations.models import Station


@login_required
def inventory_by_delivery_view(request):
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut accéder à cette page.")
        return redirect("account:not_access")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "date_desc").strip() or "date_desc"

    allowed_stations = Station.objects.filter(owner=request.user).order_by("name")

    deliveries_qs = (
        Delivery.objects.select_related(
            "order_supplier",
            "order_supplier__order",
            "order_supplier__order__station",
            "order_supplier__supplier",
        )
        .filter(order_supplier__order__station__in=allowed_stations)
    )

    if station_filter:
        deliveries_qs = deliveries_qs.filter(order_supplier__order__station_id=station_filter)

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None
    if date_from:
        deliveries_qs = deliveries_qs.filter(delivery_date__gte=date_from)
    if date_to:
        deliveries_qs = deliveries_qs.filter(delivery_date__lte=date_to)

    if search_query:
        deliveries_qs = deliveries_qs.filter(
            Q(order_supplier__order__station__name__icontains=search_query)
            | Q(order_supplier__supplier__name__icontains=search_query)
            | Q(truck_number__icontains=search_query)
            | Q(driver_name__icontains=search_query)
        )

    # Montant livré (selon prix unitaire de la commande)
    delivered_amount_expr = ExpressionWrapper(
        (F("delivered_qty_gasoline") * F("order_supplier__unit_price_gasoline"))
        + (F("delivered_qty_diesel") * F("order_supplier__unit_price_diesel")),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    deliveries_qs = deliveries_qs.annotate(delivered_amount=delivered_amount_expr)

    stats = deliveries_qs.aggregate(
        total_gasoline=Sum("delivered_qty_gasoline"),
        total_diesel=Sum("delivered_qty_diesel"),
        total_amount=Sum("delivered_amount"),
    )
    total_gasoline = stats["total_gasoline"] or Decimal("0")
    total_diesel = stats["total_diesel"] or Decimal("0")
    total_amount = stats["total_amount"] or Decimal("0")

    sort_map = {
        "date_desc": ("-delivery_date", "-id"),
        "date_asc": ("delivery_date", "id"),
        "amount_desc": ("-delivered_amount", "-delivery_date"),
        "amount_asc": ("delivered_amount", "-delivery_date"),
        "station_asc": ("order_supplier__order__station__name", "-delivery_date"),
        "station_desc": ("-order_supplier__order__station__name", "-delivery_date"),
    }
    deliveries_qs = deliveries_qs.order_by(*sort_map.get(sort, sort_map["date_desc"]))

    paginator = Paginator(deliveries_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "deliveries": page_obj.object_list,
        "page_obj": page_obj,
        "stations": allowed_stations,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "sort": sort,
        "total_deliveries": deliveries_qs.count(),
        "total_gasoline": total_gasoline,
        "total_diesel": total_diesel,
        "total_amount": total_amount,
    }
    return render(request, "inventory_content.html", context)


@login_required
def compare_receptions_vs_sales_view(request):
    """
    Comparaison entrées (réceptions/livraisons) vs sorties (ventes),
    pour évaluer la rentabilité sur une période.
    """
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut accéder à cette page.")
        return redirect("account:not_access")

    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()

    allowed_stations = Station.objects.filter(owner=request.user).order_by("name")

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    # Réceptions (livraisons) = ce qui rentre
    deliveries_qs = (
        Delivery.objects.select_related(
            "order_supplier",
            "order_supplier__order",
            "order_supplier__order__station",
        )
        .filter(order_supplier__order__station__in=allowed_stations)
    )
    if station_filter:
        deliveries_qs = deliveries_qs.filter(
            order_supplier__order__station_id=station_filter
        )
    if date_from:
        deliveries_qs = deliveries_qs.filter(delivery_date__gte=date_from)
    if date_to:
        deliveries_qs = deliveries_qs.filter(delivery_date__lte=date_to)

    delivered_amount_expr = ExpressionWrapper(
        (F("delivered_qty_gasoline") * F("order_supplier__unit_price_gasoline"))
        + (F("delivered_qty_diesel") * F("order_supplier__unit_price_diesel")),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    deliveries_qs = deliveries_qs.annotate(delivered_amount=delivered_amount_expr)
    reception_stats = deliveries_qs.aggregate(
        qty_gasoline=Sum("delivered_qty_gasoline"),
        qty_diesel=Sum("delivered_qty_diesel"),
        amount=Sum("delivered_amount"),
    )

    receptions_qty_gasoline = reception_stats["qty_gasoline"] or Decimal("0")
    receptions_qty_diesel = reception_stats["qty_diesel"] or Decimal("0")
    receptions_amount = reception_stats["amount"] or Decimal("0")

    # Ventes = ce qui sort
    sales_qs = Sale.objects.select_related("station").filter(
        station__in=allowed_stations
    )
    if station_filter:
        sales_qs = sales_qs.filter(station_id=station_filter)
    if date_from:
        sales_qs = sales_qs.filter(sale_date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(sale_date__lte=date_to)

    sale_stats = sales_qs.aggregate(
        qty_gasoline=Sum("qty_gasoline"),
        qty_diesel=Sum("qty_diesel"),
        amount=Sum("total_amount"),
    )

    sales_qty_gasoline = sale_stats["qty_gasoline"] or Decimal("0")
    sales_qty_diesel = sale_stats["qty_diesel"] or Decimal("0")
    sales_amount = sale_stats["amount"] or Decimal("0")

    margin = sales_amount - receptions_amount
    margin_rate = Decimal("0")
    if receptions_amount and receptions_amount != Decimal("0"):
        margin_rate = (margin / receptions_amount) * Decimal("100")

    context = {
        "stations": allowed_stations,
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "receptions_qty_gasoline": receptions_qty_gasoline,
        "receptions_qty_diesel": receptions_qty_diesel,
        "receptions_amount": receptions_amount,
        "sales_qty_gasoline": sales_qty_gasoline,
        "sales_qty_diesel": sales_qty_diesel,
        "sales_amount": sales_amount,
        "margin": margin,
        "margin_rate": margin_rate,
        "deliveries_count": deliveries_qs.count(),
        "sales_count": sales_qs.count(),
    }
    return render(request, "compare_inventory_and_daily_stock.html", context)
