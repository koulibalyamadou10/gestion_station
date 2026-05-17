from django.db import models
from django.utils import timezone


class Inventory(models.Model):
    """
    Historique des niveaux de cuves : chaque ligne enregistre les quantités essence / gasoil
    **après** l'opération (création station, vente pompes, etc.), alignées sur Station.stock_*.
    Pour le stock à une date donnée, on utilise la dernière ligne jusqu'à cette date
    (voir inventory.views._system_stock_from_inventory_cumulative et _system_stock_for_daily_compare).
    """

    SOURCE_BULK_READING = "bulk_reading"
    SOURCE_SALE = "sale"
    SOURCE_STATION_INIT = "station_init"
    SOURCE_CHOICES = [
        (SOURCE_BULK_READING, "Saisie groupée pompes"),
        (SOURCE_SALE, "Vente (lecture unitaire)"),
        (SOURCE_STATION_INIT, "Création station"),
    ]

    station = models.ForeignKey("stations.Station", on_delete=models.CASCADE)
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.CharField(max_length=32, blank=True, default="")
    reading_date = models.DateField(null=True, blank=True)
    previous_stock_gasoline = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    previous_stock_diesel = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "stock_reel"

    def __str__(self):
        return f"Inventory #{self.id} - {self.station.name}"

    @property
    def is_bulk_reading_deletable(self):
        return self.source == self.SOURCE_BULK_READING and hasattr(self, "reading_batch")


class InventoryWalletAllocation(models.Model):
    """Répartition wallet enregistrée avec une saisie groupée (pour annulation)."""

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="wallet_allocations",
    )
    account = models.ForeignKey("wallet.Account", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_reel_wallet"
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "account"],
                name="unique_inventory_wallet_allocation",
            ),
        ]

    def __str__(self):
        return f"{self.inventory_id} — {self.account_id}"
