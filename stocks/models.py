from django.db import models
import uuid

# Create your models here.
class Stock(models.Model):
    STOCK_TYPE_CHOICES = [
        ('essence', 'Essence'),
        ('gazole', 'Gazole'),
    ]
    stock_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    type = models.CharField(max_length=255, choices=STOCK_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)