from django.contrib import admin
from pumps.models import Pump, PumpReading

# Register your models here.
class PumpAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'station', 'created_at', 'updated_at')
admin.site.register(Pump, PumpAdmin)

class PumpReadingAdmin(admin.ModelAdmin):
    list_display = ('id', 'pump', 'employee', 'current_index', 'reading_date', 'created_at', 'updated_at')
admin.site.register(PumpReading, PumpReadingAdmin)