from django.urls import path
from stations.views import stations_list_view, create_station_view, delete_station_view, station_detail_view, update_station_view

app_name = 'stations'

urlpatterns = [
    path('', stations_list_view, name='stations_list'),
    path('create/', create_station_view, name='create_station'),
    path('<uuid:station_uuid>/', station_detail_view, name='station_detail'),
    path('<uuid:station_uuid>/update/', update_station_view, name='update_station'),
    path('delete/<uuid:station_uuid>/', delete_station_view, name='delete_station'),
]

