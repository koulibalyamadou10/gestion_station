from django.urls import path

from city.views import city_list_view, create_city_view, update_city_view, delete_city_view

app_name = "city"

urlpatterns = [
    path("", city_list_view, name="city_list"),
    path("create/", create_city_view, name="create_city"),
    path("<int:city_id>/update/", update_city_view, name="update_city"),
    path("<int:city_id>/delete/", delete_city_view, name="delete_city"),
]
