from django.contrib import admin
from sale.models import Sale

# Register your models here.
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'station', 'pump_reading', 'sale_date', 'qty_gasoline', 'qty_diesel', 'unit_price_gasoline', 'unit_price_diesel', 'total_amount', 'recorded_by', 'created_at', 'updated_at')
admin.site.register(Sale, SaleAdmin)