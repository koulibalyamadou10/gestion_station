from django.urls import path

from deposit.views import delete_deposit_view, deposit_list_view, update_deposit_view

app_name = "deposit"

urlpatterns = [
    path("", deposit_list_view, name="deposit_list"),
    path("<int:pk>/update/", update_deposit_view, name="deposit_update"),
    path("<int:pk>/delete/", delete_deposit_view, name="deposit_delete"),
]
