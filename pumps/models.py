from django.db import models
import uuid 

# Create your models here.
class Pump(models.Model):
    pump_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)