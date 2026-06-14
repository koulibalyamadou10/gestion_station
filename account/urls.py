from django.urls import path
from account.views import (
    login_view, dashboard_view, logout_view, 
    users_list_view, not_access_view, create_user_view, delete_user_view,
    managers_list_view, create_manager_view, create_admin_view, admins_list_view,
    update_admin_name_view, delete_admin_view, toggle_admin_status_view,
    reset_admin_password_view, delete_manager_view,
    profile_view, change_password_view, user_detail_view,
    update_manager_name_view, update_user_name_view, toggle_manager_status_view,
    reset_manager_password_view, update_manager_station_view
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
    path('admins/', admins_list_view, name='admins_list'),
    path('managers/create/', create_manager_view, name='create_manager'),
    path('admins/create/', create_admin_view, name='create_admin'),
    path('admins/update/<uuid:user_uuid>/', update_admin_name_view, name='update_admin_name'),
    path('admins/toggle-status/<uuid:user_uuid>/', toggle_admin_status_view, name='toggle_admin_status'),
    path('admins/reset-password/<uuid:user_uuid>/', reset_admin_password_view, name='reset_admin_password'),
    path('admins/delete/<uuid:user_uuid>/', delete_admin_view, name='delete_admin'),
    path('managers/update/<uuid:user_uuid>/', update_manager_name_view, name='update_manager_name'),
    path('managers/toggle-status/<uuid:user_uuid>/', toggle_manager_status_view, name='toggle_manager_status'),
    path('managers/reset-password/<uuid:user_uuid>/', reset_manager_password_view, name='reset_manager_password'),
    path('managers/update-station/<uuid:user_uuid>/', update_manager_station_view, name='update_manager_station'),
    path('managers/delete/<uuid:user_uuid>/', delete_manager_view, name='delete_manager'),
    path('users/update/<uuid:user_uuid>/', update_user_name_view, name='update_user_name'),
    path('profile/', profile_view, name='profile'),
    path('profile/change-password/', change_password_view, name='change_password'),
    path('not-access/', not_access_view, name='not_access'),
]

