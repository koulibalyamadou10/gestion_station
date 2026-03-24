import uuid
from decimal import Decimal

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

    order_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
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

    @property
    def estimated_line_total(self):
        """Total estimé (première ligne order_suppliers), pour listes / récap."""
        line = self.order_suppliers.first()
        if not line:
            return Decimal("0")
        qg = line.qty_gasoline if line.qty_gasoline is not None else Decimal("0")
        qd = line.qty_diesel if line.qty_diesel is not None else Decimal("0")
        pg = (
            line.unit_price_gasoline
            if line.unit_price_gasoline is not None
            else Decimal("0")
        )
        pd = (
            line.unit_price_diesel
            if line.unit_price_diesel is not None
            else Decimal("0")
        )
        return qg * pg + qd * pd


class OrderSupplier(models.Model):
    order_supplier_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_suppliers')
    supplier = models.ForeignKey('supplier.Supplier', on_delete=models.CASCADE, related_name='order_suppliers', null=True, blank=True)
    qty_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qty_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_gasoline = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price_diesel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "order_suppliers"

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else "Sans fournisseur"
        return f"Order #{self.order_id} - {supplier_name}"
