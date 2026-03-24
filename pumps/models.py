from django.db import models
import uuid

# Create your models here.
class Pump(models.Model):
    pump_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    name = models.CharField(max_length=100)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pumps"

    def __str__(self):
        return self.name

# historiques
class PumpReading(models.Model):
    pump_reading_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name='readings')
    employee = models.ForeignKey('employee.Employee', on_delete=models.SET_NULL, null=True, blank=True)
    current_index = models.DecimalField(max_digits=12, decimal_places=2)
    reading_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pump_readings"

    def __str__(self):
        return f"{self.pump.name} - {self.reading_date}"


class PumpReset(models.Model):
    pump_reset_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name="resets")
    previous_initial_index = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    previous_current_index = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reset_initial_index = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reset_current_index = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.TextField(null=True, blank=True)
    reset_by = models.ForeignKey("account.CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pump_resets"

    def __str__(self):
        return f"Reset {self.pump.name} - {self.created_at:%Y-%m-%d %H:%M}"
