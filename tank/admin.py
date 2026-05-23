from django.contrib import admin

from tank.models import Tank


@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ("name", "station", "product", "actual_quantity", "created_at")
    list_filter = ("product", "station")
    search_fields = ("name", "station__name")
