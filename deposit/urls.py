from django.urls import path

from deposit.views import deposit_list_view

app_name = "deposit"

urlpatterns = [
    path("", deposit_list_view, name="deposit_list"),
]
