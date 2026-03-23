from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from pumps.models import PumpReading
from sale.models import Sale
from stations.models import Station, StationManager


@login_required
def sale_list_view(request):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'acceder a cette page.")
        return redirect("account:dashboard")

    if request.user.role == "admin":
        allowed_stations = Station.objects.filter(owner=request.user).order_by("name")
    else:
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager:
            messages.error(request, "Aucune station ne vous est assignee.")
            return redirect("account:dashboard")
        allowed_stations = Station.objects.filter(id=station_manager.station_id)

    if request.method == "POST":
        station_id = request.POST.get("station_id", "").strip()
        pump_reading_id = request.POST.get("pump_reading_id", "").strip()
        sale_date = request.POST.get("sale_date", "").strip()
        qty_gasoline_raw = request.POST.get("qty_gasoline", "0").strip() or "0"
        qty_diesel_raw = request.POST.get("qty_diesel", "0").strip() or "0"
        unit_price_gasoline_raw = request.POST.get("unit_price_gasoline", "0").strip() or "0"
        unit_price_diesel_raw = request.POST.get("unit_price_diesel", "0").strip() or "0"

        if not station_id or not pump_reading_id or not sale_date:
            messages.error(request, "Veuillez remplir les champs obligatoires.")
            return redirect("sale:sale_list")

        station = allowed_stations.filter(id=station_id).first()
        if not station:
            messages.error(request, "Station invalide.")
            return redirect("sale:sale_list")

        pump_reading = PumpReading.objects.filter(id=pump_reading_id, pump__station=station).first()
        if not pump_reading:
            messages.error(request, "Lecture de pompe invalide pour cette station.")
            return redirect("sale:sale_list")

        try:
            qty_gasoline = Decimal(qty_gasoline_raw)
            qty_diesel = Decimal(qty_diesel_raw)
            unit_price_gasoline = Decimal(unit_price_gasoline_raw)
            unit_price_diesel = Decimal(unit_price_diesel_raw)
        except InvalidOperation:
            messages.error(request, "Les quantites et prix doivent etre numeriques.")
            return redirect("sale:sale_list")

        if qty_gasoline < 0 or qty_diesel < 0 or unit_price_gasoline < 0 or unit_price_diesel < 0:
            messages.error(request, "Les valeurs negatives ne sont pas autorisees.")
            return redirect("sale:sale_list")

        total_amount = (qty_gasoline * unit_price_gasoline) + (qty_diesel * unit_price_diesel)

        Sale.objects.create(
            station=station,
            pump_reading=pump_reading,
            sale_date=sale_date,
            qty_gasoline=qty_gasoline,
            qty_diesel=qty_diesel,
            unit_price_gasoline=unit_price_gasoline,
            unit_price_diesel=unit_price_diesel,
            total_amount=total_amount,
            recorded_by=request.user,
        )
        messages.success(request, "Vente enregistree avec succes.")
        return redirect("sale:sale_list")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("sale_date", "").strip()

    sales_queryset = Sale.objects.select_related(
        "station", "pump_reading", "pump_reading__pump", "recorded_by"
    ).order_by("-sale_date", "-created_at")

    if request.user.role == "admin":
        sales_queryset = sales_queryset.filter(station__in=allowed_stations)
    else:
        sales_queryset = sales_queryset.filter(station=allowed_stations.first())

    if search_query:
        sales_queryset = sales_queryset.filter(
            Q(station__name__icontains=search_query)
            | Q(pump_reading__pump__name__icontains=search_query)
            | Q(recorded_by__first_name__icontains=search_query)
            | Q(recorded_by__last_name__icontains=search_query)
        )

    if station_filter:
        sales_queryset = sales_queryset.filter(station_id=station_filter)

    if date_filter:
        sales_queryset = sales_queryset.filter(sale_date=date_filter)

    paginator = Paginator(sales_queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    stats = sales_queryset.aggregate(
        total_amount=Sum("total_amount"),
        total_gasoline=Sum("qty_gasoline"),
        total_diesel=Sum("qty_diesel"),
    )

    pump_readings = PumpReading.objects.select_related("pump", "pump__station").filter(
        pump__station__in=allowed_stations
    ).order_by("-reading_date", "-created_at")

    context = {
        "sales": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "stations": allowed_stations,
        "pump_readings": pump_readings,
        "total_sales": sales_queryset.count(),
        "total_amount": stats["total_amount"] or Decimal("0"),
        "total_gasoline": stats["total_gasoline"] or Decimal("0"),
        "total_diesel": stats["total_diesel"] or Decimal("0"),
    }
    return render(request, "sale_content.html", context)
