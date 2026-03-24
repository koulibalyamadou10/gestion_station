from django.urls import path

from order.views import (
    order_detail_view,
    order_list_view,
    update_order_quantities_view,
)

app_name = "order"

urlpatterns = [
    path("", order_list_view, name="order_list"),
    path("<int:order_id>/", order_detail_view, name="order_detail"),
    path(
        "<int:order_id>/update-quantities/",
        update_order_quantities_view,
        name="update_order_quantities",
    ),
]
