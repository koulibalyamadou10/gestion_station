from django.contrib import admin
from delivery.models import Delivery

# Register your models here.
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_supplier', 'delivery_date', 'delivered_qty_gasoline', 'delivered_qty_diesel', 'missing_qty_gasoline', 'missing_qty_diesel', 'created_at', 'updated_at')
admin.site.register(Delivery, DeliveryAdmin)