from django.db import models


class DailyStock(models.Model):
    station = models.ForeignKey("stations.Station", on_delete=models.CASCADE)
    recorded_by = models.ForeignKey("account.CustomUser", on_delete=models.CASCADE)
    stock_date = models.DateField()
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    previous_stock_gasoline = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    previous_stock_diesel = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
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


class DailyStockTankLine(models.Model):
    """Relevé par cuve au moment de l'entrée (pour annulation / restauration)."""

    daily_stock = models.ForeignKey(
        DailyStock,
        on_delete=models.CASCADE,
        related_name="tank_lines",
    )
    tank = models.ForeignKey("tank.Tank", on_delete=models.CASCADE)
    previous_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    recorded_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_cuve_ligne"
        constraints = [
            models.UniqueConstraint(
                fields=["daily_stock", "tank"],
                name="unique_daily_stock_tank_line",
            ),
        ]

    def __str__(self):
        return f"{self.daily_stock_id} — {self.tank_id}"
