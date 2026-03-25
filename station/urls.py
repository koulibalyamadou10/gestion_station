"""
URL configuration for station project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render

def view_home(request):
    return render(request, 'home.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', view_home, name='home'),
    path('', include('account.urls')),
    
    path('stations/', include('stations.urls')),
    path('employees/', include('employee.urls')),
    path('positions/', include('position.urls')),
    path('cities/', include('city.urls')),
    path('pumps/', include('pumps.urls')),
    path('sales/', include('sale.urls')),
    path('wallets/', include('wallet.urls')),
    path('suppliers/', include('supplier.urls')),
    path('orders/', include('order.urls')),
    path('expenses/', include('expense.urls')),
    path('deposits/', include('deposit.urls')),
    path('daily-stock/', include('daily_stock.urls')),
    path('inventory/', include('inventory.urls')),
]
