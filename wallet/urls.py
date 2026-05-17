from django.urls import path

from wallet.views import (
    delete_wallet_view,
    transfer_wallet_view,
    update_wallet_view,
    wallet_detail_view,
    wallet_list_view,
)

app_name = "wallet"

urlpatterns = [
    path("", wallet_list_view, name="wallet_list"),
    path("<uuid:uuid>/", wallet_detail_view, name="wallet_detail"),
    path("transfer/", transfer_wallet_view, name="transfer_wallet"),
    path("delete/<uuid:uuid>/", delete_wallet_view, name="delete_wallet"),
    path("update/<uuid:uuid>/", update_wallet_view, name="update_wallet"),
]
