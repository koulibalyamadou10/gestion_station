from django.urls import path

from expense.views import delete_expense_view, expense_list_view, update_expense_view

app_name = "expense"

urlpatterns = [
    path("", expense_list_view, name="expense_list"),
    path("<int:pk>/update/", update_expense_view, name="expense_update"),
    path("<int:pk>/delete/", delete_expense_view, name="expense_delete"),
]
