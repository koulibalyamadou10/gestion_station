from django.db import models

class Inventory(models.Model):
    """
    Historique des niveaux de cuves : chaque ligne enregistre les quantités essence / gasoil
    **après** l’opération (création station, vente pompes, etc.), alignées sur Station.stock_*.
    Pour le stock à une date donnée, on utilise la dernière ligne jusqu’à cette date
    (voir inventory.views._system_stock_from_inventory_cumulative).
    """

    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory"

    def __str__(self):
        return f"Inventory #{self.id} - {self.station.name}"
