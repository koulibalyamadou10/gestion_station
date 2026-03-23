from django.db import models

class Sale(models.Model):
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    pump_reading = models.ForeignKey('pumps.PumpReading', on_delete=models.CASCADE)
    sale_date = models.DateField()
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sales"

    def __str__(self):
        return f"Sale #{self.id} - {self.sale_date}"
