from django.urls import path

from sale.views import sale_detail_view, sale_list_view

app_name = "sale"

urlpatterns = [
    path("", sale_list_view, name="sale_list"),
    path("<int:station_id>/<str:sale_date>/", sale_detail_view, name="sale_detail"),
]
