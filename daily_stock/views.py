from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from sale.models import Sale
from stations.models import Station, StationManager


def _sales_scope_for_user(user):
    if user.role == "admin":
        return Sale.objects.filter(station__owner=user), Station.objects.filter(owner=user).order_by("name")
    if user.role == "manager":
        station_manager = (
            StationManager.objects.filter(manager=user).select_related("station").first()
        )
        if not station_manager:
            return None, None
        return Sale.objects.filter(station=station_manager.station), Station.objects.filter(id=station_manager.station_id)
    return None, None


@login_required
def daily_sales_view(request):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    base_qs, allowed_stations = _sales_scope_for_user(request.user)
    if base_qs is None:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "date_desc").strip() or "date_desc"

    sales_qs = base_qs.select_related("station").all()

    if request.user.role == "admin" and station_filter:
        sales_qs = sales_qs.filter(station_id=station_filter)

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None
    if date_from:
        sales_qs = sales_qs.filter(sale_date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(sale_date__lte=date_to)

    if search_query:
        sales_qs = sales_qs.filter(
            Q(station__name__icontains=search_query)
        )

    # Stats globales (sur toutes les ventes filtrées)
    stats = sales_qs.aggregate(
        total_amount=Sum("total_amount"),
        total_gasoline=Sum("qty_gasoline"),
        total_diesel=Sum("qty_diesel"),
    )

    total_sales = sales_qs.count()
    total_amount = stats["total_amount"] or Decimal("0")
    total_gasoline = stats["total_gasoline"] or Decimal("0")
    total_diesel = stats["total_diesel"] or Decimal("0")

    # Groupage journalier
    daily_qs = (
        sales_qs.values("sale_date", "station_id", "station__name")
        .annotate(
            day_amount=Sum("total_amount"),
            day_gasoline=Sum("qty_gasoline"),
            day_diesel=Sum("qty_diesel"),
            day_sales_count=Count("id"),
        )
    )

    # Tri
    sort_map = {
        "date_desc": ("-sale_date", "-station__name"),
        "date_asc": ("sale_date", "station__name"),
        "amount_desc": ("-day_amount", "-sale_date"),
        "amount_asc": ("day_amount", "-sale_date"),
        "station_asc": ("station__name", "-sale_date"),
        "station_desc": ("-station__name", "-sale_date"),
    }
    ordering = sort_map.get(sort, sort_map["date_desc"])
    daily_qs = daily_qs.order_by(*ordering)

    paginator = Paginator(daily_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "stations": allowed_stations,
        "show_station_filter": request.user.role == "admin",
        "search_query": search_query,
        "station_filter": station_filter,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
        "sort": sort,
        "total_sales": total_sales,
        "total_amount": total_amount,
        "total_gasoline": total_gasoline,
        "total_diesel": total_diesel,
    }
    return render(request, "daily_stock.html", context)
