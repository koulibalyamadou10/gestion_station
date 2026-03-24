from django.urls import path

from expense.views import expense_list_view

app_name = "expense"

urlpatterns = [
    path("", expense_list_view, name="expense_list"),
]
