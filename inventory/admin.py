from django.contrib import admin

from inventory.models import Inventory, InventoryWalletAllocation


class InventoryWalletAllocationInline(admin.TabularInline):
    model = InventoryWalletAllocation
    extra = 0
    readonly_fields = ("account", "amount", "created_at")


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "station",
        "source",
        "reading_date",
        "qty_gasoline",
        "qty_diesel",
        "created_at",
        "updated_at",
    )
    list_filter = ("station", "source")
    search_fields = ("station__name",)
    readonly_fields = (
        "previous_stock_gasoline",
        "previous_stock_diesel",
        "updated_at",
    )
    inlines = [InventoryWalletAllocationInline]
    date_hierarchy = "created_at"
