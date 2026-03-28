from django.contrib import admin
from product_price.models import ProductPrice

# Register your models here.
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ('id', 'effective_from', 'price_gasoline', 'price_diesel', 'created_at', 'updated_at')
admin.site.register(ProductPrice, ProductPriceAdmin)