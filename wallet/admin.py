from django.contrib import admin

from wallet.models import Account, AccountHistory


@admin.register(Account)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "station", "name", "balance", "currency", "created_at", "updated_at")


@admin.register(AccountHistory)
class AccountHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "from_account",
        "to_account",
        "amount",
        "currency",
        "recorded_by",
        "created_at",
    )
    list_filter = ("currency", "created_at")
    search_fields = ("from_account__name", "to_account__name")
    readonly_fields = ("uuid", "created_at")