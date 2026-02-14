from django.urls import path
from stations.views import stations_list_view, create_station_view, delete_station_view, station_detail_view

app_name = 'stations'

urlpatterns = [
    path('', stations_list_view, name='stations_list'),
    path('create/', create_station_view, name='create_station'),
    path('<int:station_id>/', station_detail_view, name='station_detail'),
    path('delete/<int:station_id>/', delete_station_view, name='delete_station'),
]

