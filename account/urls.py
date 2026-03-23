from django.urls import path
from account.views import (
    login_view, dashboard_view, logout_view, 
    users_list_view, not_access_view, create_user_view, delete_user_view,
    managers_list_view, create_manager_view, delete_manager_view,
    profile_view, change_password_view, user_detail_view,
    update_manager_name_view, update_user_name_view, toggle_manager_status_view,
    reset_manager_password_view
)

app_name = 'account'

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('users/', users_list_view, name='users_list'),
    path('users/<uuid:user_uuid>/', user_detail_view, name='user_detail'),
    path('users/create/', create_user_view, name='create_user'),
    path('users/delete/<uuid:user_uuid>/', delete_user_view, name='delete_user'),
    path('managers/', managers_list_view, name='managers_list'),
    path('managers/create/', create_manager_view, name='create_manager'),
    path('managers/update/<uuid:user_uuid>/', update_manager_name_view, name='update_manager_name'),
    path('managers/toggle-status/<uuid:user_uuid>/', toggle_manager_status_view, name='toggle_manager_status'),
    path('managers/reset-password/<uuid:user_uuid>/', reset_manager_password_view, name='reset_manager_password'),
    path('managers/delete/<uuid:user_uuid>/', delete_manager_view, name='delete_manager'),
    path('users/update/<uuid:user_uuid>/', update_user_name_view, name='update_user_name'),
    path('profile/', profile_view, name='profile'),
    path('profile/change-password/', change_password_view, name='change_password'),
    path('not-access/', not_access_view, name='not_access'),
]

