from django.db import models
import uuid

class Employee(models.Model):
    employee_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    position = models.ForeignKey('position.Position', on_delete=models.SET_NULL, null=True, blank=True)
    station = models.ForeignKey('stations.Station', on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey('account.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    # owner = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE, related_name='owner_employees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employees"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
