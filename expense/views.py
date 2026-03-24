from decimal import Decimal, InvalidOperation
from typing import Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect, render

from expense.models import Expense
from stations.models import Station, StationManager
from wallet.models import Account

# Libellés affichés dans le select (8 catégories pour une station-service + « Autre »)
EXPENSE_CATEGORY_LABELS = [
    "Maintenance & équipements",
    "Achats carburant / stock",
    "Salaires & charges sociales",
    "Loyer & charges locatives",
    "Eau, électricité & télécom",
    "Fournitures & consommables",
    "Taxes, redevances & assurances",
    "Autre",
]


class InsufficientBalanceError(Exception):
    """Raised when wallet balance is too low for the expense."""


def _normalize_category(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw in EXPENSE_CATEGORY_LABELS:
        return raw
    return None


@login_required
def expense_list_view(request):
    """
    Liste des dépenses + création (modal) réservée aux gérants (manager).
    Les administrateurs voient la liste (toutes leurs stations) sans pouvoir créer.
    """
    if request.user.role not in ("admin", "manager"):
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    manager_station = None
    station_manager = None

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

    # --- POST : création uniquement par un manager ---
    if request.method == "POST":
        if request.user.role != "manager":
            messages.error(request, "Seul un gérant peut enregistrer une dépense.")
            return redirect("expense:expense_list")

        account_id = request.POST.get("account_id", "").strip()
        amount_raw = request.POST.get("amount", "").strip()
        expense_date = request.POST.get("expense_date", "").strip()
        category = _normalize_category(request.POST.get("category", ""))
        description = request.POST.get("description", "").strip() or None
        currency = request.POST.get("currency", "GNF").strip() or "GNF"

        accounts_qs = Account.objects.filter(station=manager_station).select_related(
            "station"
        )

        if not category:
            messages.error(request, "Veuillez sélectionner une catégorie de dépense.")
            return redirect("expense:expense_list")

        if not account_id or not amount_raw or not expense_date:
            messages.error(request, "Wallet, montant et date sont obligatoires.")
            return redirect("expense:expense_list")

        account = accounts_qs.filter(pk=account_id).first()
        if not account:
            messages.error(request, "Wallet invalide pour votre station.")
            return redirect("expense:expense_list")

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant invalide.")
            return redirect("expense:expense_list")

        if amount <= 0:
            messages.error(request, "Le montant doit être supérieur à 0.")
            return redirect("expense:expense_list")

        current_balance = account.balance or Decimal("0")
        if current_balance < amount:
            messages.error(
                request,
                "Solde du wallet insuffisant pour enregistrer cette dépense.",
            )
            return redirect("expense:expense_list")

        try:
            with transaction.atomic():
                acc = Account.objects.select_for_update().get(pk=account.pk)
                if acc.station_id != manager_station.id:
                    raise ValueError("invalid_wallet")
                if (acc.balance or Decimal("0")) < amount:
                    raise InsufficientBalanceError()
                Expense.objects.create(
                    account=acc,
                    amount=amount,
                    currency=currency,
                    expense_date=expense_date,
                    category=category,
                    description=description,
                    recorded_by=request.user,
                )
                acc.balance = (acc.balance or Decimal("0")) - amount
                acc.save(update_fields=["balance", "updated_at"])
        except InsufficientBalanceError:
            messages.error(
                request,
                "Solde du wallet insuffisant pour enregistrer cette dépense.",
            )
            return redirect("expense:expense_list")
        except ValueError as exc:
            if str(exc) == "invalid_wallet":
                messages.error(request, "Wallet invalide pour votre station.")
            else:
                messages.error(request, f"Erreur : {exc}")
            return redirect("expense:expense_list")
        except Exception as exc:
            messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
            return redirect("expense:expense_list")

        messages.success(request, "Dépense enregistrée et wallet mis à jour.")
        return redirect("expense:expense_list")

    # --- GET : liste ---
    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    date_filter = request.GET.get("expense_date", "").strip()
    page_number = request.GET.get("page")

    if request.user.role == "admin":
        expenses_qs = (
            Expense.objects.filter(account__station__owner=request.user)
            .select_related("account", "account__station", "recorded_by")
            .order_by("-expense_date", "-created_at")
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
        expenses_qs = (
            Expense.objects.filter(account__station_id=manager_station.id)
            .select_related("account", "account__station", "recorded_by")
            .order_by("-expense_date", "-created_at")
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
        expenses_qs = expenses_qs.filter(
            Q(description__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(account__name__icontains=search_query)
        )
    if station_filter and request.user.role == "admin":
        expenses_qs = expenses_qs.filter(account__station_id=station_filter)
    if date_filter:
        expenses_qs = expenses_qs.filter(expense_date=date_filter)

    paginator = Paginator(expenses_qs, 10)
    page_obj = paginator.get_page(page_number)

    stats = expenses_qs.aggregate(total_amount=Sum("amount"))

    default_account = accounts_qs.first() if request.user.role == "manager" else None

    context = {
        "expenses": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "date_filter": date_filter,
        "stations": stations,
        "accounts": accounts_qs,
        "total_expenses": expenses_qs.count(),
        "sum_amount": stats["total_amount"] or Decimal("0"),
        "can_create_expense": request.user.role == "manager",
        "show_station_filter": show_station_filter,
        "show_station_column": show_station_column,
        "manager_station": manager_station,
        "default_account_id": default_account.pk if default_account else None,
        "expense_categories": EXPENSE_CATEGORY_LABELS,
    }
    return render(request, "expense_content.html", context)
