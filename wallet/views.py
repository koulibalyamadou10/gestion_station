import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from stations.models import Station
from wallet.models import Account, normalize_account_name


@login_required
def wallet_list_view(request):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'acceder a cette page.")
        return redirect("account:not_access")

    station_scope = Station.objects.filter(owner=request.user).order_by("name")
    wallets_queryset = Account.objects.select_related("station").filter(station__in=station_scope).order_by("-created_at")

    if request.method == "POST":
        station_id = request.POST.get("station_id", "").strip()
        name_raw = request.POST.get("name", "")
        balance_raw = request.POST.get("balance", "0").strip() or "0"
        currency = request.POST.get("currency", "GNF").strip() or "GNF"
        balance_raw = balance_raw.replace(" ", "").replace("\u00a0", "").replace(",", ".")

        if not station_id:
            messages.error(request, "La station est obligatoire.")
            return redirect("wallet:wallet_list")

        station = station_scope.filter(id=station_id).first()
        if not station:
            messages.error(request, "Station invalide.")
            return redirect("wallet:wallet_list")

        name = normalize_account_name(name_raw)
        if not name:
            messages.error(request, "Le nom du wallet est obligatoire.")
            return redirect("wallet:wallet_list")
        if not re.fullmatch(r"[A-Z ]+", name):
            messages.error(request, "Le nom ne doit contenir que des lettres et des espaces.")
            return redirect("wallet:wallet_list")

        if Account.objects.filter(station=station, name=name).exists():
            messages.error(
                request,
                f'Un wallet nom "{name}" existe deja pour cette station.',
            )
            return redirect("wallet:wallet_list")

        try:
            balance = Decimal(balance_raw)
        except InvalidOperation:
            messages.error(request, "Le solde initial doit etre numerique.")
            return redirect("wallet:wallet_list")

        if balance < 0:
            messages.error(request, "Le solde initial ne peut pas etre negatif.")
            return redirect("wallet:wallet_list")

        try:
            Account.objects.create(
                station=station,
                name=name,
                balance=balance,
                currency=currency,
            )
        except IntegrityError:
            messages.error(
                request,
                f'Un wallet nom "{name}" existe deja pour cette station.',
            )
            return redirect("wallet:wallet_list")

        messages.success(request, "Wallet cree avec succes.")
        return redirect("wallet:wallet_list")

    search_query = request.GET.get("search", "").strip()
    station_filter = request.GET.get("station", "").strip()
    page_number = request.GET.get("page")

    if search_query:
        wallets_queryset = wallets_queryset.filter(
            Q(station__name__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(currency__icontains=search_query)
        )

    if station_filter:
        wallets_queryset = wallets_queryset.filter(station_id=station_filter)

    paginator = Paginator(wallets_queryset, 10)
    page_obj = paginator.get_page(page_number)

    stats = wallets_queryset.aggregate(
        total_balance=Sum("balance"),
    )

    context = {
        "wallets": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "station_filter": station_filter,
        "stations": station_scope,
        "total_wallets": wallets_queryset.count(),
        "total_balance": stats["total_balance"] or Decimal("0"),
    }
    return render(request, "wallet_content.html", context)


@login_required
def delete_wallet_view(request, uuid):
    if request.method != "POST":
        return redirect("wallet:wallet_list")

    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission de supprimer un wallet.")
        return redirect("account:not_access")

    wallet = get_object_or_404(Account, uuid=uuid)

    if wallet.station.owner != request.user:
        messages.error(request, "Vous n'avez pas la permission de supprimer ce wallet.")
        return redirect("wallet:wallet_list")

    if wallet.balance != Decimal("0"):
        messages.error(request, "Suppression impossible: le solde du wallet doit etre a 0.")
        return redirect("wallet:wallet_list")

    wallet.delete()
    messages.success(request, "Wallet supprime avec succes.")
    return redirect("wallet:wallet_list")


@login_required
def update_wallet_view(request, uuid):
    """Modification du nom du wallet uniquement (unicité par station)."""
    if request.method != "POST":
        return redirect("wallet:wallet_list")

    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission de modifier ce wallet.")
        return redirect("account:not_access")

    wallet = get_object_or_404(Account, uuid=uuid)

    if wallet.station.owner != request.user:
        messages.error(request, "Vous n'avez pas la permission de modifier ce wallet.")
        return redirect("wallet:wallet_list")

    name_raw = request.POST.get("name", "")
    name = normalize_account_name(name_raw)
    if not name:
        messages.error(request, "Le nom du wallet est obligatoire.")
        return redirect("wallet:wallet_list")
    if not re.fullmatch(r"[A-Z ]+", name):
        messages.error(request, "Le nom ne doit contenir que des lettres et des espaces.")
        return redirect("wallet:wallet_list")

    if (
        Account.objects.filter(station=wallet.station, name=name)
        .exclude(pk=wallet.pk)
        .exists()
    ):
        messages.error(
            request,
            f'Un wallet nom "{name}" existe deja pour cette station.',
        )
        return redirect("wallet:wallet_list")

    try:
        wallet.name = name
        wallet.save(update_fields=["name", "updated_at"])
    except IntegrityError:
        messages.error(
            request,
            f'Un wallet nom "{name}" existe deja pour cette station.',
        )
        return redirect("wallet:wallet_list")

    messages.success(request, "Nom du wallet mis a jour avec succes.")
    return redirect("wallet:wallet_list")
