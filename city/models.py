from django.db import models
import uuid
class City(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True)
    name = models.CharField(max_length=150, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cities"
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name
