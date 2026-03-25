from django.db import models

class Inventory(models.Model):
    """
    Historique des mouvements de stock en cuves : entrées en positif (création station,
    livraison commande), sorties en négatif (ventes via pompes). La somme algébrique
    jusqu’à une date donne le stock système à cette date (comparé au relevé DailyStock).
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
