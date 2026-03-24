from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from delivery.models import Delivery
from order.models import Order, OrderSupplier
from stations.models import Station, StationManager
from supplier.models import Supplier


def _clean_decimal(raw_value: str, default: str = "0") -> Decimal:
    raw = (raw_value or default).strip() or default
    normalized = raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return Decimal(normalized)


def _order_scope_for_user(user):
    if user.role == "admin":
        return Order.objects.filter(station__owner=user), None
    if user.role == "manager":
        station_manager = (
            StationManager.objects.filter(manager=user).select_related("station").first()
        )
        if not station_manager:
            return None, None
        return Order.objects.filter(station=station_manager.station), station_manager.station
    return None, None


@login_required
def order_list_view(request):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    manager_station = None
    if request.user.role == "manager":
        station_manager = (
            StationManager.objects.filter(manager=request.user)
            .select_related("station")
            .first()
        )
        if not station_manager:
            messages.error(request, "Aucune station ne vous est assignée.")
            return redirect("account:dashboard")
        manager_station = station_manager.station

    if request.method == "POST":
        if request.user.role != "manager":
            messages.error(request, "Seul un gérant peut créer une commande.")
            return redirect("order:order_list")

        order_date = request.POST.get("order_date", "").strip()
        notes = request.POST.get("notes", "").strip() or None
        qty_gasoline_raw = request.POST.get("qty_gasoline", "0").strip() or "0"
        qty_diesel_raw = request.POST.get("qty_diesel", "0").strip() or "0"
        unit_price_gasoline_raw = (
            request.POST.get("unit_price_gasoline", "0").strip() or "0"
        )
        unit_price_diesel_raw = (
            request.POST.get("unit_price_diesel", "0").strip() or "0"
        )

        if not order_date:
            messages.error(request, "La date de commande est obligatoire.")
            return redirect("order:order_list")

        try:
            qty_gasoline = _clean_decimal(qty_gasoline_raw)
            qty_diesel = _clean_decimal(qty_diesel_raw)
            unit_price_gasoline = _clean_decimal(unit_price_gasoline_raw)
            unit_price_diesel = _clean_decimal(unit_price_diesel_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Les quantités et prix doivent être numériques.")
            return redirect("order:order_list")

        if qty_gasoline < 0 or qty_diesel < 0 or unit_price_gasoline < 0 or unit_price_diesel < 0:
            messages.error(request, "Les valeurs négatives ne sont pas autorisées.")
            return redirect("order:order_list")

        if qty_gasoline == 0 and qty_diesel == 0:
            messages.error(request, "Ajoutez au moins une quantité (essence ou gasoil).")
            return redirect("order:order_list")

        try:
            with transaction.atomic():
                order = Order.objects.create(
                    station=manager_station,
                    status=Order.STATUS_PENDING,
                    order_date=order_date,
                    notes=notes,
                )
                OrderSupplier.objects.create(
                    order=order,
                    supplier=None,  # fournisseur non renseigné à la création
                    qty_gasoline=qty_gasoline,
                    qty_diesel=qty_diesel,
                    unit_price_gasoline=unit_price_gasoline,
                    unit_price_diesel=unit_price_diesel,
                )
        except Exception as exc:
            messages.error(request, f"Erreur lors de la création : {exc}")
            return redirect("order:order_list")

        messages.success(request, "Commande créée avec statut En attente.")
        return redirect("order:order_list")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("order_date", "").strip()
    status_filter = request.GET.get("status", "").strip()
    page_number = request.GET.get("page")

    suppliers_for_confirm = []
    if request.user.role == "admin":
        orders_qs = (
            Order.objects.filter(station__owner=request.user)
            .select_related("station")
            .prefetch_related("order_suppliers")
            .order_by("-order_date", "-created_at")
        )
        stations = Station.objects.filter(owner=request.user).order_by("name")
        show_station_filter = True
        show_station_column = True
        suppliers_for_confirm = list(Supplier.objects.order_by("name"))
    else:
        orders_qs = (
            Order.objects.filter(station=manager_station)
            .select_related("station")
            .prefetch_related("order_suppliers")
            .order_by("-order_date", "-created_at")
        )
        stations = []
        station_filter = ""
        show_station_filter = False
        show_station_column = False

    if search_query:
        orders_qs = orders_qs.filter(
            Q(notes__icontains=search_query)
            | Q(station__name__icontains=search_query)
            | Q(status__icontains=search_query)
        )
    if station_filter and request.user.role == "admin":
        orders_qs = orders_qs.filter(station_id=station_filter)
    if date_filter:
        orders_qs = orders_qs.filter(order_date=date_filter)
    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)

    paginator = Paginator(orders_qs, 10)
    page_obj = paginator.get_page(page_number)

    pending_count = orders_qs.filter(status=Order.STATUS_PENDING).count()
    confirmed_count = orders_qs.filter(status=Order.STATUS_CONFIRMED).count()
    delivered_count = orders_qs.filter(status=Order.STATUS_DELIVERED).count()
    cancelled_count = orders_qs.filter(status=Order.STATUS_CANCELLED).count()

    context = {
        "orders": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "status_filter": status_filter,
        "stations": stations,
        "total_orders": orders_qs.count(),
        "show_station_filter": show_station_filter,
        "show_station_column": show_station_column,
        "can_create_order": request.user.role == "manager",
        "can_edit_order_quantities": request.user.role in ("admin", "manager"),
        "manager_station": manager_station,
        "status_choices": Order.STATUS_CHOICES,
        "pending_count": pending_count,
        "confirmed_count": confirmed_count,
        "delivered_count": delivered_count,
        "cancelled_count": cancelled_count,
        "default_order_price_essence": getattr(
            settings, "PRODUCT_PRICE_AT_ORDER_ESSENCE", 0
        ),
        "default_order_price_diesel": getattr(
            settings, "PRODUCT_PRICE_AT_ORDER_DIESEL", 0
        ),
        "can_admin_orders": request.user.role == "admin",
        "suppliers_for_confirm": suppliers_for_confirm,
    }
    return render(request, "order_content.html", context)


@login_required
def order_detail_view(request, order_uuid):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    scoped_qs, manager_station = _order_scope_for_user(request.user)
    if scoped_qs is None:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")

    order = get_object_or_404(
        scoped_qs.select_related("station").prefetch_related("order_suppliers"),
        order_uuid=order_uuid,
    )
    order_supplier = order.order_suppliers.first()
    total_estimated = Decimal("0")
    if order_supplier:
        total_estimated = (
            (order_supplier.qty_gasoline or Decimal("0"))
            * (order_supplier.unit_price_gasoline or Decimal("0"))
        ) + (
            (order_supplier.qty_diesel or Decimal("0"))
            * (order_supplier.unit_price_diesel or Decimal("0"))
        )

    context = {
        "order": order,
        "order_supplier": order_supplier,
        "manager_station": manager_station,
        "total_estimated": total_estimated,
        "can_edit_order": request.user.role in ("admin", "manager")
        and order.status == Order.STATUS_PENDING,
    }
    return render(request, "order_detail.html", context)


@login_required
def update_order_quantities_view(request, order_uuid):
    if request.method != "POST":
        return redirect("order:order_list")

    if request.user.role not in ("admin", "manager"):
        messages.error(
            request,
            "Seuls l’administrateur ou le gérant peuvent modifier une commande.",
        )
        return redirect("order:order_list")

    scoped_qs, _ = _order_scope_for_user(request.user)
    if scoped_qs is None:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")

    order = get_object_or_404(scoped_qs.prefetch_related("order_suppliers"), order_uuid=order_uuid)
    if order.status != Order.STATUS_PENDING:
        messages.error(request, "Seules les commandes en attente peuvent être modifiées.")
        return redirect("order:order_list")

    order_supplier = order.order_suppliers.first()
    if not order_supplier:
        messages.error(request, "Aucune ligne de commande trouvée.")
        return redirect("order:order_list")

    qty_gasoline_raw = request.POST.get("qty_gasoline", "0")
    qty_diesel_raw = request.POST.get("qty_diesel", "0")
    unit_price_gasoline_raw = request.POST.get("unit_price_gasoline", "0")
    unit_price_diesel_raw = request.POST.get("unit_price_diesel", "0")
    notes = request.POST.get("notes", "").strip() or None

    try:
        qty_gasoline = _clean_decimal(qty_gasoline_raw)
        qty_diesel = _clean_decimal(qty_diesel_raw)
        unit_price_gasoline = _clean_decimal(unit_price_gasoline_raw)
        unit_price_diesel = _clean_decimal(unit_price_diesel_raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Les quantités et prix doivent être numériques.")
        return redirect("order:order_list")

    if qty_gasoline < 0 or qty_diesel < 0 or unit_price_gasoline < 0 or unit_price_diesel < 0:
        messages.error(request, "Les valeurs négatives ne sont pas autorisées.")
        return redirect("order:order_list")

    if qty_gasoline == 0 and qty_diesel == 0:
        messages.error(request, "Ajoutez au moins une quantité (essence ou gasoil).")
        return redirect("order:order_list")

    with transaction.atomic():
        order.notes = notes
        order.save(update_fields=["notes", "updated_at"])
        order_supplier.qty_gasoline = qty_gasoline
        order_supplier.qty_diesel = qty_diesel
        order_supplier.unit_price_gasoline = unit_price_gasoline
        order_supplier.unit_price_diesel = unit_price_diesel
        order_supplier.save(
            update_fields=[
                "qty_gasoline",
                "qty_diesel",
                "unit_price_gasoline",
                "unit_price_diesel",
                "updated_at",
            ]
        )

    messages.success(request, "Commande mise à jour avec succès.")
    return redirect("order:order_list")


@login_required
def order_delete_view(request, order_uuid):
    if request.method != "POST":
        return redirect("order:order_list")

    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut supprimer une commande.")
        return redirect("order:order_list")

    orders_qs = Order.objects.filter(station__owner=request.user)
    order = get_object_or_404(orders_qs, order_uuid=order_uuid)

    if order.status != Order.STATUS_PENDING:
        messages.error(request, "Seules les commandes en attente peuvent être supprimées.")
        return redirect("order:order_list")

    ref = f"#{order.id}"
    order.delete()
    messages.success(request, f"Commande {ref} supprimée.")
    return redirect("order:order_list")


@login_required
def order_confirm_view(request, order_uuid):
    if request.method != "POST":
        return redirect("order:order_list")

    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut confirmer une commande.")
        return redirect("order:order_list")

    orders_qs = Order.objects.filter(station__owner=request.user).prefetch_related(
        "order_suppliers"
    )
    order = get_object_or_404(orders_qs, order_uuid=order_uuid)

    if order.status != Order.STATUS_PENDING:
        messages.error(request, "Seules les commandes en attente peuvent être confirmées.")
        return redirect("order:order_list")

    order_supplier = order.order_suppliers.first()
    if not order_supplier:
        messages.error(request, "Aucune ligne de commande trouvée.")
        return redirect("order:order_list")

    supplier_id = (request.POST.get("supplier_id") or "").strip()
    if not supplier_id:
        messages.error(request, "Vous devez choisir un fournisseur.")
        return redirect("order:order_list")

    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if Delivery.objects.filter(order_supplier=order_supplier).exists():
        messages.error(request, "Une livraison est déjà enregistrée pour cette commande.")
        return redirect("order:order_list")

    with transaction.atomic():
        order_supplier.supplier = supplier
        order_supplier.save(update_fields=["supplier", "updated_at"])
        order.status = Order.STATUS_CONFIRMED
        order.save(update_fields=["status", "updated_at"])
        Delivery.objects.create(
            order_supplier=order_supplier,
            delivered_qty_gasoline=order_supplier.qty_gasoline,
            delivered_qty_diesel=order_supplier.qty_diesel,
            delivery_date=timezone.now().date(),
        )

    messages.success(
        request,
        f"Commande #{order.id} confirmée avec le fournisseur « {supplier.name} ».",
    )
    return redirect("order:order_list")
