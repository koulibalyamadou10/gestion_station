from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from product_price.models import ProductPrice


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
        if parsed_date <= today:
            messages.error(
                request,
                "La date d'application doit être postérieure à la date du jour (à partir de demain).",
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

    prices = ProductPrice.objects.all()
    min_effective_date = timezone.now().date() + timedelta(days=1)
    context = {
        "prices": prices,
        "min_effective_date": min_effective_date,
    }
    return render(request, "product_price_content.html", context)
