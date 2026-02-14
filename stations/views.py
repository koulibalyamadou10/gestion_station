from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from stations.models import Station
from permissions_web import admin_required, super_admin_required

@login_required
def stations_list_view(request):
    """
    Vue pour afficher la liste des stations
    Accessible aux admins et super_admins
    """
    # Récupérer les stations selon le rôle
    if request.user.role == 'super_admin':
        # Le super_admin voit toutes les stations
        stations = Station.objects.all().order_by('-created_at')
    elif request.user.role == 'admin':
        # L'admin voit uniquement ses propres stations
        stations = Station.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
        return redirect('dashboard')
    
    # Statistiques
    total_stations = stations.count()
    
    # Filtres et recherche
    search_query = request.GET.get('search', '')
    city_filter = request.GET.get('city', '')
    
    # Appliquer les filtres
    if search_query:
        stations = stations.filter(
            Q(name__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query)
        )
    
    if city_filter:
        stations = stations.filter(city__icontains=city_filter)
    
    # Statistiques filtrées
    filtered_count = stations.count()
    
    # Liste des villes uniques pour le filtre
    cities = Station.objects.values_list('city', flat=True).distinct().order_by('city')
    
    context = {
        'stations': stations,
        'total_stations': total_stations,
        'filtered_count': filtered_count,
        'search_query': search_query,
        'city_filter': city_filter,
        'cities': cities,
    }
    
    return render(request, 'stations/stations_list.html', context)
