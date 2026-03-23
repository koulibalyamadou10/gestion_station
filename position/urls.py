from django.urls import path

from position.views import (
    create_position_view,
    delete_position_view,
    position_list_view,
    update_position_view,
)

app_name = "position"

urlpatterns = [
    path("", position_list_view, name="position_list"),
    path("create/", create_position_view, name="create_position"),
    path("<uuid:uuid>/update/", update_position_view, name="update_position"),
    path("<uuid:uuid>/delete/", delete_position_view, name="delete_position"),
]
