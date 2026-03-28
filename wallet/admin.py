from django.contrib import admin
from wallet.models import Account

# Register your models here.
class WalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'station', 'name', 'balance', 'currency', 'created_at', 'updated_at')
admin.site.register(Account, WalletAdmin)