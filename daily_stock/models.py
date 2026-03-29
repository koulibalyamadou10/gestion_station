from django.db import models

class DailyStock(models.Model):
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    stock_date = models.DateField()
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "stock"
        constraints = [
            models.UniqueConstraint(
                fields=["station", "stock_date"],
                name="unique_daily_stock_station_date",
            ),
        ]

    def __str__(self):
        return f"Daily Stock #{self.id} - {self.stock_date}"
