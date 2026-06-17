from django.db import models
import uuid

# Create your models here.
class Entry(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    motif = models.TextField(null=True, blank=True)
    date = models.DateField()
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "entries"

    def __str__(self):
        return f"Entry #{self.id} - {self.amount}"