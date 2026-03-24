from django.db import models
import uuid

class Supplier(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, null=True, blank=True)
    name = models.CharField(max_length=150)
    contact = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "suppliers"

    def __str__(self):
        return self.name
