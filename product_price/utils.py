"""Utilitaires pour les grilles tarifaires (hors vues HTTP)."""

from product_price.models import ProductPrice


def get_product_price_for_date(d):
    """
    Dernière grille applicable à la date ``d`` : plus grande ``effective_from``
    parmi les lignes avec ``effective_from <= d``.
    Retourne ``ProductPrice`` ou ``None``.
    """
    if d is None:
        return None
    return (
        ProductPrice.objects.filter(effective_from__lte=d)
        .order_by("-effective_from")
        .first()
    )
