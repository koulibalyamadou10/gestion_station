from django.db import models

class Inventory(models.Model):
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory"

    def __str__(self):
        return f"Inventory #{self.id} - {self.station.name}"
