from django.urls import path
from pumps.views import (
    pumps_list_view, create_pump_view, update_pump_view,
    delete_pump_view, pump_detail_view, create_reading_view
)

app_name = 'pumps'

urlpatterns = [
    path('', pumps_list_view, name='pumps_list'),
    path('create/', create_pump_view, name='create_pump'),
    path('<int:pump_id>/', pump_detail_view, name='pump_detail'),
    path('<int:pump_id>/update/', update_pump_view, name='update_pump'),
    path('<int:pump_id>/reading/', create_reading_view, name='create_reading'),
    path('delete/<int:pump_id>/', delete_pump_view, name='delete_pump'),
]

