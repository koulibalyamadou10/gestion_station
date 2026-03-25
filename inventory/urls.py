from django.urls import path

from inventory.views import compare_receptions_vs_sales_view, inventory_by_delivery_view

app_name = "inventory"

urlpatterns = [
    path("stock-livre/", inventory_by_delivery_view, name="stock_livre"),
    path("rentabilite/", compare_receptions_vs_sales_view, name="compare_profit"),
]
