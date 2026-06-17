from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from entry.models import Entry
from stations.models import Station, StationManager
from wallet.models import Account


def _normalize_amount_raw(raw: str) -> str:
    return (raw or "").replace(" ", "").replace("\u00a0", "").replace(",", ".")


def _accounts_for_user(user, manager_station=None):
    if user.role == "admin":
        return (
            Account.objects.filter(station__owner=user)
            .select_related("station")
            .order_by("station__name", "name")
        )
    return (
        Account.objects.filter(station=manager_station)
        .select_related("station")
        .order_by("name")
    )


def _entry_queryset_for_user(user, manager_station=None):
    if user.role == "admin":
        return (
            Entry.objects.filter(account__station__owner=user)
            .select_related("account", "account__station", "recorded_by")
            .order_by("-date", "-created_at")
        )
    return (
        Entry.objects.filter(account__station=manager_station)
        .select_related("account", "account__station", "recorded_by")
        .order_by("-date", "-created_at")
    )


def _account_allowed(user, account, manager_station=None):
    if user.role == "admin":
        return account.station.owner_id == user.id
    return account.station_id == manager_station.id


@login_required
def entry_list_view(request):
    """Liste des entrées + création (admin et gérant)."""
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

    accounts_qs = _accounts_for_user(request.user, manager_station)

    if request.method == "POST":
        account_id = request.POST.get("account_id", "").strip()
        amount_raw = request.POST.get("amount", "").strip()
        entry_date = request.POST.get("date", "").strip()
        motif = request.POST.get("motif", "").strip() or None

        if not account_id or not amount_raw or not entry_date:
            messages.error(request, "Compte, montant et date sont obligatoires.")
            return redirect("entry:entry_list")

        account = accounts_qs.filter(pk=account_id).first()
        if not account:
            messages.error(request, "Compte invalide.")
            return redirect("entry:entry_list")

        amount_raw = _normalize_amount_raw(amount_raw)
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant invalide.")
            return redirect("entry:entry_list")

        if amount <= 0:
            messages.error(request, "Le montant doit être supérieur à 0.")
            return redirect("entry:entry_list")

        parsed_date = parse_date(entry_date)
        if not parsed_date:
            messages.error(request, "Date invalide.")
            return redirect("entry:entry_list")

        try:
            with transaction.atomic():
                acc = Account.objects.select_for_update().get(pk=account.pk)
                if not _account_allowed(request.user, acc, manager_station):
                    raise ValueError("invalid_wallet")

                Entry.objects.create(
                    account=acc,
                    amount=amount,
                    motif=motif,
                    date=parsed_date,
                    recorded_by=request.user,
                )
                acc.balance = (acc.balance or Decimal("0")) + amount
                acc.save(update_fields=["balance", "updated_at"])
        except ValueError:
            messages.error(request, "Compte invalide pour votre périmètre.")
            return redirect("entry:entry_list")
        except Exception as exc:
            messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
            return redirect("entry:entry_list")

        messages.success(request, "Entrée enregistrée : le compte a été crédité.")
        return redirect("entry:entry_list")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("entry_date", "").strip()
    page_number = request.GET.get("page")

    entries_qs = _entry_queryset_for_user(request.user, manager_station)

    if request.user.role == "admin":
        stations = Station.objects.filter(owner=request.user).order_by("name")
        show_station_filter = True
        show_station_column = True
    else:
        stations = []
        show_station_filter = False
        show_station_column = False
        station_filter = ""

    if search_query:
        entries_qs = entries_qs.filter(
            Q(motif__icontains=search_query)
            | Q(account__name__icontains=search_query)
            | Q(recorded_by__first_name__icontains=search_query)
            | Q(recorded_by__last_name__icontains=search_query)
        )
    if station_filter and request.user.role == "admin":
        entries_qs = entries_qs.filter(account__station_id=station_filter)
    if date_filter:
        entries_qs = entries_qs.filter(date=date_filter)

    paginator = Paginator(entries_qs, 10)
    page_obj = paginator.get_page(page_number)
    stats = entries_qs.aggregate(total_amount=Sum("amount"))
    default_account = accounts_qs.first()

    context = {
        "entries": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "stations": stations,
        "accounts": accounts_qs,
        "total_entries": entries_qs.count(),
        "sum_amount": stats["total_amount"] or Decimal("0"),
        "show_station_filter": show_station_filter,
        "show_station_column": show_station_column,
        "manager_station": manager_station,
        "default_account_id": default_account.pk if default_account else None,
        "can_create_entry": True,
        "can_edit_entry": True,
        "can_delete_entry": request.user.role == "admin",
        "today": timezone.now().date(),
    }
    return render(request, "entry_content.html", context)


def _resolve_manager_station(user):
    station_manager = (
        StationManager.objects.filter(manager=user)
        .select_related("station")
        .first()
    )
    if not station_manager:
        return None
    return station_manager.station


@login_required
def update_entry_view(request, pk):
    """Modification d'une entrée avec ajustement du solde du (des) compte(s)."""
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission de modifier une entrée.")
        return redirect("entry:entry_list")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("entry:entry_list")

    manager_station = None
    if request.user.role == "manager":
        manager_station = _resolve_manager_station(request.user)
        if not manager_station:
            messages.error(request, "Aucune station ne vous est assignée.")
            return redirect("account:dashboard")
        entry = get_object_or_404(
            Entry.objects.select_related("account"),
            pk=pk,
            account__station=manager_station,
        )
    else:
        entry = get_object_or_404(
            Entry.objects.select_related("account", "account__station"),
            pk=pk,
            account__station__owner=request.user,
        )

    accounts_qs = _accounts_for_user(request.user, manager_station)

    account_id = request.POST.get("account_id", "").strip()
    amount_raw = request.POST.get("amount", "").strip()
    entry_date = request.POST.get("date", "").strip()
    motif = request.POST.get("motif", "").strip() or None

    if not account_id or not amount_raw or not entry_date:
        messages.error(request, "Compte, montant et date sont obligatoires.")
        return redirect("entry:entry_list")

    new_account = accounts_qs.filter(pk=account_id).first()
    if not new_account:
        messages.error(request, "Compte invalide.")
        return redirect("entry:entry_list")

    amount_raw = _normalize_amount_raw(amount_raw)
    try:
        new_amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Montant invalide.")
        return redirect("entry:entry_list")

    if new_amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect("entry:entry_list")

    parsed_date = parse_date(entry_date)
    if not parsed_date:
        messages.error(request, "Date invalide.")
        return redirect("entry:entry_list")

    old_amount = entry.amount

    try:
        with transaction.atomic():
            ent = (
                Entry.objects.select_for_update()
                .select_related("account")
                .get(pk=entry.pk)
            )
            old_acc = Account.objects.select_for_update().get(pk=ent.account_id)
            new_acc = Account.objects.select_for_update().get(pk=new_account.pk)

            if not _account_allowed(request.user, old_acc, manager_station):
                raise ValueError("invalid_wallet")
            if not _account_allowed(request.user, new_acc, manager_station):
                raise ValueError("invalid_wallet")

            old_bal = old_acc.balance or Decimal("0")
            if old_bal < old_amount:
                raise ValueError("insufficient_balance")

            old_acc.balance = old_bal - old_amount
            old_acc.save(update_fields=["balance", "updated_at"])

            if new_acc.pk == old_acc.pk:
                new_acc.refresh_from_db()

            new_bal = new_acc.balance or Decimal("0")
            new_acc.balance = new_bal + new_amount
            new_acc.save(update_fields=["balance", "updated_at"])

            ent.account = new_acc
            ent.amount = new_amount
            ent.date = parsed_date
            ent.motif = motif
            ent.save()
    except Entry.DoesNotExist:
        messages.error(request, "Entrée introuvable.")
        return redirect("entry:entry_list")
    except ValueError as exc:
        if str(exc) == "invalid_wallet":
            messages.error(request, "Compte invalide pour votre périmètre.")
        elif str(exc) == "insufficient_balance":
            messages.error(
                request,
                "Solde insuffisant sur le compte pour ajuster cette entrée "
                "(réduction ou changement de compte).",
            )
        else:
            messages.error(request, str(exc))
        return redirect("entry:entry_list")
    except Exception as exc:
        messages.error(request, f"Erreur lors de la modification : {exc}")
        return redirect("entry:entry_list")

    messages.success(request, "Entrée modifiée : le solde du compte a été mis à jour.")
    return redirect("entry:entry_list")


@login_required
def delete_entry_view(request, pk):
    """Suppression d'une entrée — réservée à l'admin. Débite le compte du montant."""
    if request.user.role != "admin":
        messages.error(request, "Seul un administrateur peut supprimer une entrée.")
        return redirect("entry:entry_list")

    if request.method != "POST":
        messages.error(request, "Méthode non autorisée.")
        return redirect("entry:entry_list")

    entry = get_object_or_404(
        Entry.objects.select_related("account", "account__station"),
        pk=pk,
        account__station__owner=request.user,
    )

    amount = entry.amount
    try:
        with transaction.atomic():
            acc = Account.objects.select_for_update().get(pk=entry.account_id)
            if acc.station.owner_id != request.user.id:
                messages.error(request, "Compte invalide.")
                return redirect("entry:entry_list")

            bal = acc.balance or Decimal("0")
            if bal < amount:
                messages.error(
                    request,
                    "Impossible de supprimer : le solde du compte est insuffisant pour annuler cette entrée.",
                )
                return redirect("entry:entry_list")

            acc.balance = bal - amount
            acc.save(update_fields=["balance", "updated_at"])
            entry.delete()
    except Exception as exc:
        messages.error(request, f"Erreur lors de la suppression : {exc}")
        return redirect("entry:entry_list")

    messages.success(
        request,
        "Entrée supprimée : le montant a été débité du compte.",
    )
    return redirect("entry:entry_list")
