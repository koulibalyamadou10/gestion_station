from django.urls import path

from supplier.views import supplier_delete_view, supplier_list_view, supplier_update_view

app_name = "supplier"

urlpatterns = [
    path("", supplier_list_view, name="supplier_list"),
    path("<int:supplier_id>/modifier/", supplier_update_view, name="supplier_update"),
    path("<int:supplier_id>/supprimer/", supplier_delete_view, name="supplier_delete"),
]
