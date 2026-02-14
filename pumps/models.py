from django.db import models
import uuid 

# Create your models here.
class Pump(models.Model):
    PUMP_TYPE_CHOICES = [
        ('essence', 'Essence'),
        ('gazole', 'Gazole'),
    ]

    pump_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255, choices=PUMP_TYPE_CHOICES)
    initial_index = models.IntegerField()
    current_index = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# historiques
class PumpReading(models.Model):
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name='readings')
    previous_index = models.DecimalField(max_digits=12, decimal_places=2)
    current_index = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_sold = models.DecimalField(max_digits=12, decimal_places=2)
    reading_date = models.DateField()
    created_by = models.ForeignKey('account.CustomUser', on_delete=models.SET_NULL, null=True) # role = manager
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pump.name} - {self.reading_date}"
