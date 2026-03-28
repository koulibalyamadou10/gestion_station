from django.contrib import admin
from daily_stock.models import DailyStock

# Register your models here.
class DailyStockAdmin(admin.ModelAdmin):
    list_display = ('id', 'station', 'recorded_by', 'stock_date', 'qty_gasoline', 'qty_diesel', 'notes', 'created_at', 'updated_at')
admin.site.register(DailyStock, DailyStockAdmin)