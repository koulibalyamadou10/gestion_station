from django.urls import path

from credit.views import credit_detail_view, credit_list_view, credit_refund_view

app_name = "credit"

urlpatterns = [
    path("", credit_list_view, name="credit_list"),
    path("<uuid:credit_uuid>/", credit_detail_view, name="credit_detail"),
    path("<uuid:credit_uuid>/refund/", credit_refund_view, name="credit_refund"),
]
