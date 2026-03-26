from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from product_price.models import ProductPrice


def _product_price_in_effect_for_date(today):
    """Grille appliquée aujourd’hui : plus récente parmi celles avec effective_from ≤ today."""
    return (
        ProductPrice.objects.filter(effective_from__lte=today)
        .order_by("-effective_from")
        .first()
    )


def _normalize_decimal_input(raw):
    """Accepte saisie « 12 000 » ou « 12 000,50 » (espaces insécables inclus)."""
    if raw is None:
        return ""
    s = str(raw).replace("\u00a0", " ").replace(" ", "").replace(",", ".").strip()
    return s


@login_required
def product_price_list_view(request):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:dashboard")

    if request.method == "POST":
        effective_raw = request.POST.get("effective_from", "").strip()
        pg_raw = _normalize_decimal_input(request.POST.get("price_gasoline", ""))
        pd_raw = _normalize_decimal_input(request.POST.get("price_diesel", ""))

        parsed_date = parse_date(effective_raw)
        if not parsed_date:
            messages.error(request, "Date d'application invalide.")
            return redirect("product_price:product_price_list")

        today = timezone.now().date()
        if parsed_date < today:
            messages.error(
                request,
                "La date d'application ne peut pas être dans le passé.",
            )
            return redirect("product_price:product_price_list")

        try:
            price_gasoline = Decimal(pg_raw)
            price_diesel = Decimal(pd_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Les montants doivent être des nombres valides.")
            return redirect("product_price:product_price_list")

        if price_gasoline < 0 or price_diesel < 0:
            messages.error(request, "Les prix ne peuvent pas être négatifs.")
            return redirect("product_price:product_price_list")

        try:
            ProductPrice.objects.create(
                effective_from=parsed_date,
                price_gasoline=price_gasoline,
                price_diesel=price_diesel,
            )
            messages.success(request, "La grille de prix a été créée.")
        except IntegrityError:
            messages.error(
                request,
                "Une grille de prix existe déjà pour cette date d'application.",
            )
        return redirect("product_price:product_price_list")

    today = timezone.now().date()
    prices = ProductPrice.objects.all()
    active = _product_price_in_effect_for_date(today)
    context = {
        "prices": prices,
        "today": today,
        "min_effective_date": today,
        "active_product_price_uuid": active.uuid if active else None,
    }
    return render(request, "product_price_content.html", context)


@login_required
def delete_product_price_view(request, uuid):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:dashboard")

    if request.method != "POST":
        return redirect("product_price:product_price_list")

    obj = get_object_or_404(ProductPrice, uuid=uuid)
    today = timezone.now().date()
    active = _product_price_in_effect_for_date(today)
    if active and active.uuid == obj.uuid:
        messages.error(
            request,
            "Impossible de supprimer la grille actuellement en vigueur (prix utilisés pour les ventes).",
        )
        return redirect("product_price:product_price_list")

    obj.delete()
    messages.success(request, "La grille de prix a été supprimée.")
    return redirect("product_price:product_price_list")


@login_required
def update_product_price_view(request, uuid):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:dashboard")

    if request.method != "POST":
        return redirect("product_price:product_price_list")

    obj = get_object_or_404(ProductPrice, uuid=uuid)
    today = timezone.now().date()

    # Modification autorisée uniquement pour les grilles non encore en vigueur.
    if obj.effective_from <= today:
        messages.error(
            request,
            "Seules les grilles non encore en vigueur peuvent être modifiées.",
        )
        return redirect("product_price:product_price_list")

    effective_raw = request.POST.get("effective_from", "").strip()
    pg_raw = _normalize_decimal_input(request.POST.get("price_gasoline", ""))
    pd_raw = _normalize_decimal_input(request.POST.get("price_diesel", ""))

    parsed_date = parse_date(effective_raw)
    if not parsed_date:
        messages.error(request, "Date d'application invalide.")
        return redirect("product_price:product_price_list")
    if parsed_date < today:
        messages.error(request, "La date d'application ne peut pas être dans le passé.")
        return redirect("product_price:product_price_list")

    try:
        price_gasoline = Decimal(pg_raw)
        price_diesel = Decimal(pd_raw)
    except (InvalidOperation, ValueError):
        messages.error(request, "Les montants doivent être des nombres valides.")
        return redirect("product_price:product_price_list")

    if price_gasoline < 0 or price_diesel < 0:
        messages.error(request, "Les prix ne peuvent pas être négatifs.")
        return redirect("product_price:product_price_list")

    obj.effective_from = parsed_date
    obj.price_gasoline = price_gasoline
    obj.price_diesel = price_diesel
    try:
        obj.save()
        messages.success(request, "La grille de prix a été modifiée.")
    except IntegrityError:
        messages.error(
            request,
            "Une grille de prix existe déjà pour cette date d'application.",
        )
    return redirect("product_price:product_price_list")
