from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from credit.models import Credit
from refund.models import Refund
from stations.models import Station, StationManager
from wallet.models import Account


def _credits_queryset_with_refunded_total(base_qs):
    """Somme des remboursements par crédit (évite le nom de relation inverse)."""
    refunded_subq = (
        Refund.objects.filter(credit_id=OuterRef("pk"))
        .values("credit_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return base_qs.annotate(
        refunded_total=Coalesce(Subquery(refunded_subq), Decimal("0"))
    )


def _station_scope_for_credit_user(user):
    if user.role == "admin":
        return Station.objects.filter(owner=user)
    if user.role == "manager":
        station_ids = StationManager.objects.filter(manager=user).values_list(
            "station_id", flat=True
        )
        return Station.objects.filter(id__in=station_ids)
    return Station.objects.none()


def _credit_for_user(user, credit_uuid):
    station_scope = _station_scope_for_credit_user(user)
    return (
        Credit.objects.filter(uuid=credit_uuid, inventory__station__in=station_scope)
        .select_related("inventory", "inventory__station", "recorded_by")
        .first()
    )


def _parse_amount_raw(raw):
    return (
        (raw or "0")
        .replace("\u00a0", " ")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
        or "0"
    )


def _refunded_total_for_credit(credit):
    return Refund.objects.filter(credit=credit).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0"))
    )["total"]


@login_required
def credit_list_view(request):
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

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("credit_date", "").strip()
    page_number = request.GET.get("page")

    station_scope = _station_scope_for_credit_user(request.user)

    if request.user.role == "admin":
        credits_qs = _credits_queryset_with_refunded_total(
            Credit.objects.filter(inventory__station__owner=request.user)
            .select_related("inventory", "inventory__station", "recorded_by")
            .order_by("-date", "-created_at")
        )
        stations = Station.objects.filter(owner=request.user).order_by("name")
        show_station_filter = True
        show_station_column = True
    else:
        credits_qs = _credits_queryset_with_refunded_total(
            Credit.objects.filter(inventory__station=manager_station)
            .select_related("inventory", "inventory__station", "recorded_by")
            .order_by("-date", "-created_at")
        )
        stations = []
        show_station_filter = False
        show_station_column = False
        station_filter = ""

    if search_query:
        credits_qs = credits_qs.filter(
            Q(motif__icontains=search_query)
            | Q(recorded_by__email__icontains=search_query)
            | Q(recorded_by__first_name__icontains=search_query)
            | Q(recorded_by__last_name__icontains=search_query)
        )
    if station_filter and request.user.role == "admin":
        credits_qs = credits_qs.filter(inventory__station_id=station_filter)
    if date_filter:
        credits_qs = credits_qs.filter(date=date_filter)

    stats = credits_qs.aggregate(total_amount=Sum("amount"))
    paginator = Paginator(credits_qs, 15)
    page_obj = paginator.get_page(page_number)

    accounts_qs = (
        Account.objects.filter(station__in=station_scope)
        .select_related("station")
        .order_by("station__name", "name")
    )

    context = {
        "credits": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "stations": stations,
        "total_credits": credits_qs.count(),
        "sum_amount": stats["total_amount"] or Decimal("0"),
        "show_station_filter": show_station_filter,
        "show_station_column": show_station_column,
        "manager_station": manager_station,
        "accounts": accounts_qs,
        "can_refund": True,
    }
    return render(request, "credit_content.html", context)


@login_required
def credit_refund_view(request, credit_uuid):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'effectuer un remboursement.")
        return redirect("account:not_access")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("credit:credit_list")

    credit = _credit_for_user(request.user, credit_uuid)
    if not credit or not credit.inventory_id:
        messages.error(request, "Crédit introuvable ou non autorisé.")
        return redirect("credit:credit_list")

    station = credit.inventory.station
    account_id = request.POST.get("account_id", "").strip()
    amount_raw = _parse_amount_raw(request.POST.get("amount", ""))
    refund_date_raw = request.POST.get("refund_date", "").strip()
    name = (request.POST.get("name") or "").strip()
    phone_number = (request.POST.get("phone_number") or "").strip()

    if not account_id or not refund_date_raw or not name or not phone_number:
        messages.error(
            request,
            "Compte, montant, date, nom du client et téléphone sont obligatoires.",
        )
        return redirect("credit:credit_list")

    refund_date = parse_date(refund_date_raw)
    if not refund_date:
        messages.error(request, "Date de remboursement invalide.")
        return redirect("credit:credit_list")

    try:
        amount = Decimal(amount_raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        messages.error(request, "Montant invalide.")
        return redirect("credit:credit_list")

    if amount <= 0:
        messages.error(request, "Le montant doit être strictement positif.")
        return redirect("credit:credit_list")

    account = Account.objects.filter(pk=account_id, station=station).first()
    if not account:
        messages.error(request, "Compte invalide pour la station de ce crédit.")
        return redirect("credit:credit_list")

    try:
        with transaction.atomic():
            locked_credit = Credit.objects.select_for_update().get(pk=credit.pk)
            refunded_total = _refunded_total_for_credit(locked_credit)
            remaining = (locked_credit.amount - refunded_total).quantize(Decimal("0.01"))

            if remaining <= 0:
                messages.error(request, "Ce crédit est déjà entièrement remboursé.")
                return redirect("credit:credit_list")

            if amount > remaining:
                messages.error(
                    request,
                    f"Le montant dépasse le reste à rembourser ({remaining}).",
                )
                return redirect("credit:credit_list")

            wallet = Account.objects.select_for_update().get(pk=account.pk)
            Refund.objects.create(
                amount=amount,
                date=refund_date,
                name=name,
                phone_number=phone_number,
                credit=locked_credit,
                account=wallet,
                recorded_by=request.user,
            )
            wallet.balance = (wallet.balance or Decimal("0")) + amount
            wallet.save(update_fields=["balance", "updated_at"])
    except Credit.DoesNotExist:
        messages.error(request, "Crédit introuvable.")
        return redirect("credit:credit_list")
    except Exception as exc:
        messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
        return redirect("credit:credit_list")

    if amount >= remaining:
        messages.success(request, "Remboursement enregistré — crédit soldé.")
    else:
        messages.success(
            request,
            f"Remboursement partiel enregistré ({amount} GNF). Reste à rembourser : {remaining - amount} GNF.",
        )
    return redirect("credit:credit_detail", credit_uuid=credit_uuid)


@login_required
def credit_detail_view(request, credit_uuid):
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    credit = _credit_for_user(request.user, credit_uuid)
    if not credit:
        messages.error(request, "Crédit introuvable ou non autorisé.")
        return redirect("credit:credit_list")

    refunded_total = _refunded_total_for_credit(credit)
    remaining = (credit.amount - refunded_total).quantize(Decimal("0.01"))

    refunds = (
        Refund.objects.filter(credit=credit)
        .select_related("account", "account__station", "recorded_by")
        .order_by("-date", "-created_at")
    )

    station = credit.inventory.station if credit.inventory_id else None
    accounts_qs = Account.objects.none()
    if station:
        accounts_qs = Account.objects.filter(station=station).order_by("name")

    context = {
        "credit": credit,
        "station": station,
        "refunded_total": refunded_total,
        "remaining": remaining,
        "refunds": refunds,
        "accounts": accounts_qs,
        "can_refund": remaining > 0,
        "show_station_name": request.user.role == "admin" and station is not None,
    }
    return render(request, "credit_detail.html", context)
