from django.urls import path

from daily_stock.views import (
    daily_sales_view,
    daily_stock_create_view,
    daily_stock_delete_view,
    daily_stock_detail_view,
    stock_detail_view,
)

app_name = "daily_stock"

urlpatterns = [
    path("detail/", stock_detail_view, name="stock_detail"),
    path("", daily_sales_view, name="daily_sales"),
    path("entree-stock/", daily_stock_create_view, name="daily_stock_create"),
    path("<int:pk>/", daily_stock_detail_view, name="daily_stock_detail"),
    path("<int:pk>/supprimer/", daily_stock_delete_view, name="daily_stock_delete"),
]
