from django.db import models
import uuid

# Create your models here.
class Station(models.Model):
    station_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    created_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name