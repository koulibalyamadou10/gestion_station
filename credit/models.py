from django.db import models
import uuid

# Create your models here.
class Credit(models.Model):
    """
    Correspondance des couleurs :

    🔴 unpaid → Unpaid
    🟡 partial → Partially Paid
    🟢 paid → Paid
    """
    STATUS_CHOICES = [
        ('unpaid', 'Non payé'),
        ('partial', 'Partiellement payé'),
        ('paid', 'Payé'),
    ]
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)  # champs calculé
    date = models.DateField()
    motif = models.TextField(null=True, blank=True)
    inventory = models.ForeignKey(
        'inventory.Inventory',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='credits',
    )
    recorded_by = models.ForeignKey('account.CustomUser', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Credit #{self.id} - {self.amount} GNF"

    class Meta:
        db_table = "credits"