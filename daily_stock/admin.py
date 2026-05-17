from django.contrib import admin

from daily_stock.models import DailyStock, DailyStockTankLine


class DailyStockTankLineInline(admin.TabularInline):
    model = DailyStockTankLine
    extra = 0
    readonly_fields = ("tank", "previous_quantity", "recorded_quantity", "created_at")


class DailyStockAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "station",
        "recorded_by",
        "stock_date",
        "qty_gasoline",
        "qty_diesel",
        "notes",
        "created_at",
        "updated_at",
    )
    inlines = [DailyStockTankLineInline]
    readonly_fields = (
        "previous_stock_gasoline",
        "previous_stock_diesel",
        "created_at",
        "updated_at",
    )


admin.site.register(DailyStock, DailyStockAdmin)
