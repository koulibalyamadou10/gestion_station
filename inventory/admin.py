from django.contrib import admin
from inventory.models import Inventory

class InventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'station', 'qty_gasoline', 'qty_diesel', 'updated_at', 'created_at')

admin.site.register(Inventory, InventoryAdmin)