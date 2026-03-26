from django.db import models
import uuid

class Employee(models.Model):
    employee_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    position = models.ForeignKey('position.Position', on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey('account.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employees"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class EmployeeStation(models.Model):
    employee_station_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_manager = models.BooleanField(default=False)

    class Meta:
        db_table = "employee_stations"

    def __str__(self):
        return f"{self.employee.first_name} {self.employee.last_name} - {self.station.name}"
