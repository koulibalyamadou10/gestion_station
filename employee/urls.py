from django.urls import path

from employee.views import employee_list_view, update_employee_view, delete_employee_view

app_name = "employee"

urlpatterns = [
    path("", employee_list_view, name="employee_list"),
    path("<uuid:employee_uuid>/update/", update_employee_view, name="update_employee"),
    path("<uuid:employee_uuid>/delete/", delete_employee_view, name="delete_employee"),
]
