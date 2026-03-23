from django.urls import path
from pumps.views import (
    pumps_list_view, create_pump_view, update_pump_view,
    delete_pump_view, pump_detail_view, create_reading_view, reset_pump_view,
    bulk_pump_reading_view,
)

app_name = 'pumps'

urlpatterns = [
    path('', pumps_list_view, name='pumps_list'),
    path('bulk-reading/', bulk_pump_reading_view, name='bulk_pump_reading'),
    path('create/', create_pump_view, name='create_pump'),
    path('<uuid:pump_uuid>/', pump_detail_view, name='pump_detail'),
    path('<uuid:pump_uuid>/update/', update_pump_view, name='update_pump'),
    path('<uuid:pump_uuid>/reading/', create_reading_view, name='create_reading'),
    path('<uuid:pump_uuid>/reset/', reset_pump_view, name='reset_pump'),
    path('delete/<uuid:pump_uuid>/', delete_pump_view, name='delete_pump'),
]

