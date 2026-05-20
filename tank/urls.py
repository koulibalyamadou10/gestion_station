from django.urls import path

from tank.views import create_tank_view, update_tank_max_capacity_view

app_name = "tank"

urlpatterns = [
    path("create/", create_tank_view, name="create_tank"),
    path(
        "update-max-capacity/<uuid:tank_uuid>/",
        update_tank_max_capacity_view,
        name="update_tank_max_capacity",
    ),
]
