from django.db import models

# Create your models here.
class Pump(models.Model):
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
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name='readings')
    employee = models.ForeignKey('employee.Employee', on_delete=models.SET_NULL, null=True, blank=True)
    initial_index = models.DecimalField(max_digits=12, decimal_places=2)
    current_index = models.DecimalField(max_digits=12, decimal_places=2)
    reading_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pump_readings"

    def __str__(self):
        return f"{self.pump.name} - {self.reading_date}"
