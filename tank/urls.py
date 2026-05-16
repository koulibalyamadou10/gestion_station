from django.urls import path

from tank.views import create_tank_view

app_name = "tank"

urlpatterns = [
    path("create/", create_tank_view, name="create_tank"),
]
