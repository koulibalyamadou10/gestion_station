from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from deposit.models import Deposit
from stations.models import Station, StationManager
from wallet.models import Account


@login_required
def deposit_list_view(request):
    """Liste des versements + création en popup (gérant). Modification en popup via update_deposit_view."""
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

                current_balance = acc.balance or Decimal("0")
                if current_balance < amount:
                    raise ValueError("insufficient_balance")

                Deposit.objects.create(
                    account=acc,
                    amount=amount,
                    currency=currency,
                    receipt_file=receipt_file,
                    deposit_date=deposit_date,
                    notes=notes,
                    recorded_by=request.user,
                )
                acc.balance = current_balance - amount
                acc.save(update_fields=["balance", "updated_at"])
        except Exception as exc:
            if str(exc) == "invalid_wallet":
                messages.error(request, "Wallet invalide pour votre station.")
                return redirect("deposit:deposit_list")
            if str(exc) == "insufficient_balance":
                messages.error(
                    request,
                    "Solde insuffisant sur le compte sélectionné pour ce montant.",
                )
                return redirect("deposit:deposit_list")
            messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
            return redirect("deposit:deposit_list")

        messages.success(request, "Versement enregistré : le compte a été débité.")
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
        "can_edit_deposit": request.user.role == "manager",
        "can_delete_deposit": request.user.role == "admin",
    }
    return render(request, "deposit_content.html", context)


def _normalize_amount_raw(amount_raw: str) -> str:
    return amount_raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")


@login_required
def update_deposit_view(request, pk):
    """
    Modification d'un versement (dépense) — réservé au gérant de la station du compte.

    Solde wallet : on réintègre d'abord l'ancien montant sur le compte concerné, puis on
    débite le nouveau montant. Équivalent au delta (nouveau − ancien) sur le même compte :
    ex. 20 000 → 30 000 : débit supplémentaire de 10 000 (refus si solde insuffisant) ;
    20 000 → 10 000 : recrédit net de 10 000.
    Si un nouveau justificatif est envoyé, l'ancien fichier est supprimé du stockage avant enregistrement.
    """
    if request.user.role != "manager":
        messages.error(request, "Seul un gérant peut modifier un versement.")
        return redirect("deposit:deposit_list")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("deposit:deposit_list")

    station_manager = (
        StationManager.objects.filter(manager=request.user)
        .select_related("station")
        .first()
    )
    if not station_manager:
        messages.error(request, "Aucune station ne vous est assignée.")
        return redirect("account:dashboard")
    manager_station = station_manager.station

    deposit = get_object_or_404(
        Deposit.objects.select_related("account"),
        pk=pk,
        account__station=manager_station,
    )

    account_id = request.POST.get("account_id", "").strip()
    amount_raw = request.POST.get("amount", "").strip()
    deposit_date = request.POST.get("deposit_date", "").strip()
    notes = request.POST.get("notes", "").strip() or None
    receipt_file = request.FILES.get("receipt_file")
    currency = request.POST.get("currency", deposit.currency or "GNF").strip() or "GNF"

    if not account_id or not amount_raw or not deposit_date:
        messages.error(request, "Compte, montant et date sont obligatoires.")
        return redirect("deposit:deposit_list")

    amount_raw = _normalize_amount_raw(amount_raw)
    new_account = Account.objects.filter(
        pk=account_id, station=manager_station
    ).first()
    if not new_account:
        messages.error(request, "Compte invalide.")
        return redirect("deposit:deposit_list")

    try:
        new_amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Montant invalide.")
        return redirect("deposit:deposit_list")

    if new_amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect("deposit:deposit_list")

    parsed_date = parse_date(deposit_date)
    if not parsed_date:
        messages.error(request, "Date invalide.")
        return redirect("deposit:deposit_list")

    old_amount = deposit.amount

    try:
        with transaction.atomic():
            dep = (
                Deposit.objects.select_for_update()
                .select_related("account")
                .get(pk=deposit.pk)
            )
            old_acc = Account.objects.select_for_update().get(pk=dep.account_id)
            new_acc = Account.objects.select_for_update().get(pk=new_account.pk)

            if old_acc.station_id != manager_station.id or new_acc.station_id != manager_station.id:
                raise ValueError("invalid_wallet")

            # 1) Réintégrer l'ancien débit (le wallet reçoit de nouveau l'ancien montant)
            old_bal = old_acc.balance or Decimal("0")
            old_acc.balance = old_bal + old_amount
            old_acc.save(update_fields=["balance", "updated_at"])

            # Même compte : deux instances ORM possibles — recharger le solde réel avant le nouveau débit
            if new_acc.pk == old_acc.pk:
                new_acc.refresh_from_db()

            # 2) Appliquer le nouveau débit (même logique qu'à la création : diminution du wallet)
            new_bal = new_acc.balance or Decimal("0")
            if new_bal < new_amount:
                raise ValueError("insufficient_balance")

            new_acc.balance = new_bal - new_amount
            new_acc.save(update_fields=["balance", "updated_at"])

            dep.account = new_acc
            dep.amount = new_amount
            dep.currency = currency
            dep.deposit_date = parsed_date
            dep.notes = notes
            if receipt_file:
                if dep.receipt_file:
                    dep.receipt_file.delete(save=False)
                dep.receipt_file = receipt_file
            dep.save()
    except Deposit.DoesNotExist:
        messages.error(request, "Versement introuvable.")
        return redirect("deposit:deposit_list")
    except Exception as exc:
        if str(exc) == "invalid_wallet":
            messages.error(request, "Compte invalide pour votre station.")
            return redirect("deposit:deposit_list")
        if str(exc) == "insufficient_balance":
            messages.error(
                request,
                "Solde insuffisant sur le compte : après réintégration de l'ancienne dépense, "
                "le solde ne permet pas de débiter le nouveau montant (par ex. si vous augmentez "
                "le versement, le compte doit couvrir ce supplément).",
            )
            return redirect("deposit:deposit_list")
        messages.error(request, f"Erreur lors de la modification : {exc}")
        return redirect("deposit:deposit_list")

    messages.success(request, "Versement modifié.")
    return redirect("deposit:deposit_list")


@login_required
def delete_deposit_view(request, pk):
    """
    Suppression d'un versement — réservé à l'admin (propriétaire des stations).
    Récrédite le compte du montant du versement (annulation du débit).
    """
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut supprimer un versement.")
        return redirect("deposit:deposit_list")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("deposit:deposit_list")

    deposit = get_object_or_404(
        Deposit.objects.select_related("account", "account__station"),
        pk=pk,
        account__station__owner=request.user,
    )

    amount = deposit.amount
    try:
        with transaction.atomic():
            acc = (
                Account.objects.select_for_update()
                .select_related("station")
                .get(pk=deposit.account_id)
            )
            if acc.station.owner_id != request.user.id:
                messages.error(request, "Compte invalide.")
                return redirect("deposit:deposit_list")

            bal = acc.balance or Decimal("0")
            acc.balance = bal + amount
            acc.save(update_fields=["balance", "updated_at"])

            if deposit.receipt_file:
                deposit.receipt_file.delete(save=False)
            deposit.delete()
    except Exception as exc:
        messages.error(request, f"Erreur lors de la suppression : {exc}")
        return redirect("deposit:deposit_list")

    messages.success(
        request,
        "Versement supprimé : le montant a été recrédité sur le compte.",
    )
    return redirect("deposit:deposit_list")
