from django.db import models
import uuid

class Position(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "postes"

    def __str__(self):
        return self.title
