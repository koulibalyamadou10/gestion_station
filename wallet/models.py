from django.db import models
import uuid

class Account(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    station = models.OneToOneField('stations.Station', on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='GNF')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"

    def __str__(self):
        return f"{self.station.name} - {self.balance} {self.currency}"
