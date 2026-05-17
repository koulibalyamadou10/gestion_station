from django.contrib import admin

from inventory.models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "station", "qty_gasoline", "qty_diesel", "created_at", "updated_at")
    list_filter = ("station",)
    search_fields = ("station__name",)
    readonly_fields = ("updated_at",)
    fields = ("station", "qty_gasoline", "qty_diesel", "created_at", "updated_at")
    date_hierarchy = "created_at"
