from django.urls import path
from stations.views import (
    stations_list_view, create_station_view, delete_station_view, 
    station_detail_view, update_station_view, get_managers_by_owner_view,
    assign_manager_view
)

app_name = 'stations'

urlpatterns = [
    path('', stations_list_view, name='stations_list'),
    path('create/', create_station_view, name='create_station'),
    path('get-managers/<int:owner_id>/', get_managers_by_owner_view, name='get_managers_by_owner'),
    path('<uuid:station_uuid>/', station_detail_view, name='station_detail'),
    path('<uuid:station_uuid>/update/', update_station_view, name='update_station'),
    path('<uuid:station_uuid>/assign-manager/', assign_manager_view, name='assign_manager'),
    path('delete/<uuid:station_uuid>/', delete_station_view, name='delete_station'),
]

