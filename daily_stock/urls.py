from django.urls import path

from daily_stock.views import daily_sales_view, daily_stock_create_view

app_name = "daily_stock"

urlpatterns = [
    path("", daily_sales_view, name="daily_sales"),
    path("entree-stock/", daily_stock_create_view, name="daily_stock_create"),
]
