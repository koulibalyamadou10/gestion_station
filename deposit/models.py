from django.db import models
import uuid

class Deposit(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='GNF')
    receipt_url = models.CharField(max_length=255, null=True, blank=True)
    deposit_date = models.DateField()
    notes = models.TextField(null=True, blank=True)
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "deposits"

    def __str__(self):
        return f"Deposit #{self.id} - {self.amount} {self.currency}"
