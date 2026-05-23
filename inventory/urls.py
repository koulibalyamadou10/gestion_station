from django.urls import path

from inventory.views import (
    compare_receptions_vs_sales_view,
    inventory_by_delivery_view,
    inventory_delete_view,
    inventory_detail_view,
)

app_name = "inventory"

urlpatterns = [
    path("stock-livre/", inventory_by_delivery_view, name="stock_livre"),
    path("rentabilite/", compare_receptions_vs_sales_view, name="compare_profit"),
    path("<int:pk>/", inventory_detail_view, name="inventory_detail"),
    path("<int:pk>/supprimer/", inventory_delete_view, name="inventory_delete"),
]
