from django.urls import path
from pumps.views import (
    pumps_list_view, create_pump_view, update_pump_view,
    delete_pump_view, pump_detail_view
)

app_name = 'pumps'

urlpatterns = [
    path('', pumps_list_view, name='pumps_list'),
    path('create/', create_pump_view, name='create_pump'),
    path('<uuid:pump_uuid>/', pump_detail_view, name='pump_detail'),
    path('<uuid:pump_uuid>/update/', update_pump_view, name='update_pump'),
    path('delete/<uuid:pump_uuid>/', delete_pump_view, name='delete_pump'),
]

