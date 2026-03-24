from django.urls import path

from order.views import (
    order_cancel_confirmed_view,
    order_confirm_view,
    order_delete_view,
    order_detail_view,
    order_list_view,
    order_mark_delivered_view,
    update_order_quantities_view,
)

app_name = "order"

urlpatterns = [
    path("", order_list_view, name="order_list"),
    path("<uuid:order_uuid>/update-quantities/", update_order_quantities_view, name="update_order_quantities"),
    path("<uuid:order_uuid>/confirmer/", order_confirm_view, name="order_confirm"),
    path("<uuid:order_uuid>/livrer/", order_mark_delivered_view, name="order_mark_delivered"),
    path(
        "<uuid:order_uuid>/annuler-confirmee/",
        order_cancel_confirmed_view,
        name="order_cancel_confirmed",
    ),
    path("<uuid:order_uuid>/supprimer/", order_delete_view, name="order_delete"),
    path("<uuid:order_uuid>/", order_detail_view, name="order_detail"),
]
