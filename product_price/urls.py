from django.urls import path

from product_price import views

app_name = "product_price"

urlpatterns = [
    path("", views.product_price_list_view, name="product_price_list"),
    path("<uuid:uuid>/delete/", views.delete_product_price_view, name="product_price_delete"),
]
