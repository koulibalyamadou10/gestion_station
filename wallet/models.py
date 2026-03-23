import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models


def normalize_account_name(value: str) -> str:
    """Majuscules, espaces internes réduits, strip."""
    if not value:
        return ""
    return " ".join(value.split()).upper()


def validate_account_name(value: str):
    """Lettres uniquement (A-Z) et espaces entre mots — valeur déjà normalisée en majuscules."""
    if not value or not value.strip():
        raise ValidationError("Le nom du wallet est obligatoire.")
    normalized = normalize_account_name(value)
    if not re.fullmatch(r"[A-Z ]+", normalized):
        raise ValidationError("Seules les lettres et les espaces sont autorisées.")


class Account(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    station = models.ForeignKey(
        "stations.Station",
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=150)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="GNF")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["station", "name"],
                name="unique_wallet_name_per_station",
            ),
        ]

    def clean(self):
        super().clean()
        if self.name:
            self.name = normalize_account_name(self.name)
        validate_account_name(self.name)

    def save(self, *args, **kwargs):
        if self.name:
            self.name = normalize_account_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.station.name}) - {self.balance} {self.currency}"
