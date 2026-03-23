from django.urls import path

from wallet.views import delete_wallet_view, wallet_list_view

app_name = "wallet"

urlpatterns = [
    path("", wallet_list_view, name="wallet_list"),
    path("delete/<uuid:wallet_uuid>/", delete_wallet_view, name="delete_wallet"),
]
