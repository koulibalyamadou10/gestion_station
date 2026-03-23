from django.db import models

class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    order_date = models.DateField()
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return f"Order #{self.id} - {self.station.name}"


class OrderSupplier(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_suppliers')
    supplier = models.ForeignKey('supplier.Supplier', on_delete=models.CASCADE)
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "order_suppliers"

    def __str__(self):
        return f"Order #{self.order_id} - {self.supplier.name}"
