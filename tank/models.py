from django.db import models
import uuid


class Tank(models.Model):
    PRODUCT_GASOLINE = "gasoline"
    PRODUCT_DIESEL = "diesel"
    PRODUCT_TYPES = [
        (PRODUCT_GASOLINE, "Essence"),
        (PRODUCT_DIESEL, "Gazoil"),
    ]

    tank_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    station = models.ForeignKey(
        "stations.Station",
        on_delete=models.CASCADE,
        related_name="tanks",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    actual_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product = models.CharField(
        max_length=100,
        choices=PRODUCT_TYPES,
        default=PRODUCT_GASOLINE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cuve_station"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_product_display_fr(self):
        return dict(self.PRODUCT_TYPES).get(self.product, self.product)
