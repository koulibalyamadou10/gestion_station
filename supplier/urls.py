from django.urls import path

from supplier.views import supplier_list_view

app_name = "supplier"

urlpatterns = [
    path("", supplier_list_view, name="supplier_list"),
]
