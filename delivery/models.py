from django.db import models
import uuid

class Delivery(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    order_supplier = models.ForeignKey('order.OrderSupplier', on_delete=models.CASCADE)
    
    delivered_qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivered_qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    missing_qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    missing_qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_date = models.DateField()
    
    truck_number = models.CharField(max_length=50, null=True, blank=True)
    driver_name = models.CharField(max_length=100, null=True, blank=True)
    driver_phone = models.CharField(max_length=100, null=True, blank=True)

    
    delivery_notes = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reception"

    def __str__(self):
        return f"Delivery #{self.id} - {self.delivery_date}"
