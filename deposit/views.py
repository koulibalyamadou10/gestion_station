from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from deposit.models import Deposit
from stations.models import Station, StationManager
from wallet.models import Account


@login_required
def deposit_list_view(request):
    """
    Liste des versements + création en popup.
    Pas de modification / suppression pour le moment.
    """
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
            messages.error(request, "Seul un gérant peut enregistrer un versement.")
            return redirect("deposit:deposit_list")

        account_id = request.POST.get("account_id", "").strip()
        amount_raw = request.POST.get("amount", "").strip()
        deposit_date = request.POST.get("deposit_date", "").strip()
        notes = request.POST.get("notes", "").strip() or None
        receipt_file = request.FILES.get("receipt_file")
        currency = request.POST.get("currency", "GNF").strip() or "GNF"

        accounts_qs = Account.objects.filter(station=manager_station)

        if not account_id or not amount_raw or not deposit_date:
            messages.error(request, "Wallet, montant et date sont obligatoires.")
            return redirect("deposit:deposit_list")
        if not receipt_file:
            messages.error(request, "Le justificatif est obligatoire.")
            return redirect("deposit:deposit_list")

        amount_raw = amount_raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")

        account = accounts_qs.filter(pk=account_id).first()
        if not account:
            messages.error(request, "Wallet invalide.")
            return redirect("deposit:deposit_list")

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant invalide.")
            return redirect("deposit:deposit_list")

        if amount <= 0:
            messages.error(request, "Le montant doit être supérieur à 0.")
            return redirect("deposit:deposit_list")

        try:
            with transaction.atomic():
                acc = Account.objects.select_for_update().get(pk=account.pk)
                if request.user.role == "manager" and acc.station_id != manager_station.id:
                    raise ValueError("invalid_wallet")

                Deposit.objects.create(
                    account=acc,
                    amount=amount,
                    currency=currency,
                    receipt_file=receipt_file,
                    deposit_date=deposit_date,
                    notes=notes,
                    recorded_by=request.user,
                )
                acc.balance = (acc.balance or Decimal("0")) + amount
                acc.save(update_fields=["balance", "updated_at"])
        except Exception as exc:
            if str(exc) == "invalid_wallet":
                messages.error(request, "Wallet invalide pour votre station.")
                return redirect("deposit:deposit_list")
            messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
            return redirect("deposit:deposit_list")

        messages.success(request, "Versement enregistré et wallet crédité.")
        return redirect("deposit:deposit_list")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("deposit_date", "").strip()
    page_number = request.GET.get("page")

    if request.user.role == "admin":
        deposits_qs = (
            Deposit.objects.filter(account__station__owner=request.user)
            .select_related("account", "account__station", "recorded_by")
            .order_by("-deposit_date", "-created_at")
        )
        stations = Station.objects.filter(owner=request.user).order_by("name")
        accounts_qs = (
            Account.objects.filter(station__owner=request.user)
            .select_related("station")
            .order_by("station__name", "name")
        )
        show_station_filter = True
        show_station_column = True
    else:
        deposits_qs = (
            Deposit.objects.filter(account__station=manager_station)
            .select_related("account", "account__station", "recorded_by")
            .order_by("-deposit_date", "-created_at")
        )
        stations = []
        accounts_qs = (
            Account.objects.filter(station=manager_station)
            .select_related("station")
            .order_by("name")
        )
        show_station_filter = False
        show_station_column = False
        station_filter = ""

    if search_query:
        deposits_qs = deposits_qs.filter(
            Q(notes__icontains=search_query) | Q(account__name__icontains=search_query)
        )
    if station_filter and request.user.role == "admin":
        deposits_qs = deposits_qs.filter(account__station_id=station_filter)
    if date_filter:
        deposits_qs = deposits_qs.filter(deposit_date=date_filter)

    paginator = Paginator(deposits_qs, 10)
    page_obj = paginator.get_page(page_number)
    stats = deposits_qs.aggregate(total_amount=Sum("amount"))
    default_account = accounts_qs.first() if accounts_qs.exists() else None

    context = {
        "deposits": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "stations": stations,
        "accounts": accounts_qs,
        "total_deposits": deposits_qs.count(),
        "sum_amount": stats["total_amount"] or Decimal("0"),
        "show_station_filter": show_station_filter,
        "show_station_column": show_station_column,
        "manager_station": manager_station,
        "default_account_id": default_account.pk if default_account else None,
        "can_create_deposit": request.user.role == "manager",
    }
    return render(request, "deposit_content.html", context)
