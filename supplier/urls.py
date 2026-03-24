from django.urls import path

from supplier.views import (
    supplier_delete_view,
    supplier_detail_view,
    supplier_list_view,
    supplier_update_view,
)

app_name = "supplier"

urlpatterns = [
    path("", supplier_list_view, name="supplier_list"),
    path("<uuid:uuid>/", supplier_detail_view, name="supplier_detail"),
    path("<uuid:uuid>/modifier/", supplier_update_view, name="supplier_update"),
    path("<uuid:uuid>/supprimer/", supplier_delete_view, name="supplier_delete"),
]
