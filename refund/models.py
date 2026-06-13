from django.db import models
import uuid 

# Create your models here.
class Refund(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=255)
    credit = models.ForeignKey('credit.Credit', on_delete=models.CASCADE)
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE)
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund #{self.id} - {self.amount} {self.currency}"

    class Meta:
        db_table = "refunds"

