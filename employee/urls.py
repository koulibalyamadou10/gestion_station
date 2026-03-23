from django.urls import path

from employee.views import employee_list_view

app_name = "employee"

urlpatterns = [
    path("", employee_list_view, name="employee_list"),
]
