from django.db import models


class ProductPrice(models.Model):
    """
    Grille tarifaire : prix essence / gazoil valables à partir d'une date donnée.
    """

    effective_from = models.DateField(
        unique=True,
        verbose_name="Date d'application",
        help_text="Date à partir de laquelle ces prix s'appliquent.",
    )
    price_gasoline = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Prix essence (par litre)",
    )
    price_diesel = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Prix gazoil (par litre)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_price"
        ordering = ["-effective_from"]
        verbose_name = "Grille de prix"
        verbose_name_plural = "Grilles de prix"

    def __str__(self):
        return f"Prix du {self.effective_from} — essence {self.price_gasoline} / gazoil {self.price_diesel}"
