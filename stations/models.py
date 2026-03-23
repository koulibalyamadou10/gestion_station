from django.db import models
import uuid

# Create your models here.
class Station(models.Model):
    station_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    name = models.CharField(max_length=150)
    city = models.ForeignKey('city.City', on_delete=models.SET_NULL, null=True, blank=True)
    address = models.TextField()
    phone = models.CharField(max_length=20, null=True, blank=True)
    owner = models.ForeignKey('account.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class StationManager(models.Model):
    station_manager_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    manager = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE) # role = manager
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.manager.get_full_name()
