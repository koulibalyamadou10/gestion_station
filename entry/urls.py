from django.urls import path

from entry.views import delete_entry_view, entry_list_view, update_entry_view

app_name = "entry"

urlpatterns = [
    path("", entry_list_view, name="entry_list"),
    path("<int:pk>/update/", update_entry_view, name="entry_update"),
    path("<int:pk>/delete/", delete_entry_view, name="entry_delete"),
]
