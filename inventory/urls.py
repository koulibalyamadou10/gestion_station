from django.urls import path

from inventory.views import inventory_by_delivery_view

app_name = "inventory"

urlpatterns = [
    path("stock-livre/", inventory_by_delivery_view, name="stock_livre"),
]
