from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name="format_gnf")
def format_gnf(value):
    """
    Affiche un montant GNF avec espaces comme séparateurs de milliers
    (ex. 12000 -> « 12 000 », 12345.50 -> « 12 345,50 »).
    """
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    neg = d < 0
    d = abs(d.quantize(Decimal("0.01")))
    int_part = int(d)
    centimes = int((d * 100) % 100)

    s = str(int_part)
    chunks = []
    while s:
        chunks.insert(0, s[-3:])
        s = s[:-3]
    formatted = " ".join(chunks)
    if neg:
        formatted = "-" + formatted
    if centimes:
        return f"{formatted},{centimes:02d}"
    return formatted
