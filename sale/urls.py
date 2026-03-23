from django.urls import path

from sale.views import sale_list_view

app_name = "sale"

urlpatterns = [
    path("", sale_list_view, name="sale_list"),
]
