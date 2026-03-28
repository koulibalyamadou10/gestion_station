"""Filtres d'affichage pour montants (séparateurs de milliers, style FR)."""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _group_thousands(whole: str) -> str:
    if not whole:
        return whole
    neg = whole.startswith("-")
    digits = whole[1:] if neg else whole
    if not digits.isdigit():
        return whole
    parts = []
    for i in range(len(digits), 0, -3):
        start = max(0, i - 3)
        parts.insert(0, digits[start:i])
    out = " ".join(parts)
    return f"-{out}" if neg else out


@register.filter(name="money_fr")
def money_fr(value):
    """
    Affiche un nombre avec séparateurs de milliers (espaces) et décimales après une virgule.
    Ex. 2400000.00 -> "2 400 000,00"
    """
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    neg = d < 0
    d = abs(d)
    s = format(d.quantize(Decimal("0.01")), "f")
    whole, frac = s.split(".", 1)
    whole_fmt = _group_thousands(whole)
    out = f"{whole_fmt},{frac}"
    return f"-{out}" if neg else out


@register.filter(name="qty_fr")
def qty_fr(value):
    """
    Quantités (litres, etc.) : séparateur de milliers par espaces.
    Pas de partie décimale affichée si elle est nulle (,00).
    Sinon virgule décimale (ex. 17 500,5).
    """
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    neg = d < 0
    d = abs(d)
    d = d.quantize(Decimal("0.01"))
    if d == d.to_integral_value():
        whole_fmt = _group_thousands(str(int(d)))
        out = whole_fmt
    else:
        s = format(d, "f")
        whole, frac = s.split(".", 1)
        whole_fmt = _group_thousands(whole)
        out = f"{whole_fmt},{frac}"
    return f"-{out}" if neg else out


@register.filter(name="money_gnf")
def money_gnf(value):
    """
    Montant en GNF : espaces comme séparateurs de milliers, suffixe GNF.
    Pas de partie décimale affichée si elle est nulle (.00).
    """
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    neg = d < 0
    d = abs(d)
    d = d.quantize(Decimal("0.01"))
    if d == d.to_integral_value():
        whole_fmt = _group_thousands(str(int(d)))
        out = f"{whole_fmt} GNF"
    else:
        s = format(d, "f")
        whole, frac = s.split(".", 1)
        whole_fmt = _group_thousands(whole)
        out = f"{whole_fmt},{frac} GNF"
    return f"-{out}" if neg else out
