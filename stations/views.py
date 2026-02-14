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
    # Vérifier les permissions
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
        return redirect('dashboard')
    
    # Récupérer toutes les stations pour les statistiques et filtres
    if request.user.role == 'super_admin':
        all_stations = Station.objects.all()
    else:
        all_stations = Station.objects.filter(created_by=request.user)
    
    # Statistiques
    total_stations = all_stations.count()
    
    # Filtres et recherche
    search_query = request.GET.get('search', '')
    city_filter = request.GET.get('city', '')
    
    # Appliquer les filtres
    stations = all_stations.order_by('-created_at')
    
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
    if request.user.role == 'super_admin':
        cities = Station.objects.values_list('city', flat=True).distinct().order_by('city')
    else:
        cities = Station.objects.filter(created_by=request.user).values_list('city', flat=True).distinct().order_by('city')
    
    # Récupérer la liste des admins pour le super_admin
    admins = None
    if request.user.role == 'super_admin':
        from account.models import CustomUser
        admins = CustomUser.objects.filter(role='admin', is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'stations': stations,
        'total_stations': total_stations,
        'filtered_count': filtered_count,
        'search_query': search_query,
        'city_filter': city_filter,
        'cities': cities,
        'admins': admins,
    }
    
    return render(request, 'stations/stations_list.html', context)

@login_required
def create_station_view(request):
    """
    Vue pour créer une nouvelle station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission de créer une station.')
        return redirect('stations_list')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        city = request.POST.get('city', '').strip()
        address = request.POST.get('address', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        longitude = request.POST.get('longitude', '').strip()
        
        # Déterminer le created_by selon le rôle
        if request.user.role == 'super_admin':
            # Le super_admin peut choisir un admin
            created_by_id = request.POST.get('created_by', '').strip()
            if not created_by_id:
                messages.error(request, 'Veuillez sélectionner un propriétaire de station.')
                return redirect('stations_list')
            
            from account.models import CustomUser
            try:
                created_by = CustomUser.objects.get(id=created_by_id, role='admin', is_active=True)
            except CustomUser.DoesNotExist:
                messages.error(request, 'Le propriétaire sélectionné est invalide.')
                return redirect('stations_list')
        else:
            # L'admin crée pour lui-même
            created_by = request.user
        
        # Validation
        if not name or not city or not address:
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
            return redirect('stations_list')
        
        if not latitude or not longitude:
            messages.error(request, 'Veuillez sélectionner un emplacement sur la carte.')
            return redirect('stations_list')
        
        try:
            # Convertir les coordonnées en Decimal
            from decimal import Decimal
            latitude_decimal = Decimal(latitude)
            longitude_decimal = Decimal(longitude)
            
            # Créer la station
            station = Station.objects.create(
                name=name,
                city=city,
                address=address,
                latitude=latitude_decimal,
                longitude=longitude_decimal,
                created_by=created_by
            )
            
            messages.success(request, f'La station "{station.name}" a été créée avec succès.')
            return redirect('stations_list')
        except ValueError:
            messages.error(request, 'Les coordonnées géographiques sont invalides.')
            return redirect('stations_list')
        except Exception as e:
            messages.error(request, f'Erreur lors de la création de la station : {str(e)}')
    
    return redirect('stations_list')

@login_required
def delete_station_view(request, station_id):
    """
    Vue pour supprimer une station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission de supprimer une station.')
        return redirect('stations_list')
    
    if request.method == 'POST':
        try:
            station = get_object_or_404(Station, id=station_id)
            
            # Vérifier les permissions
            if request.user.role == 'admin' and station.created_by != request.user:
                messages.error(request, 'Vous n\'avez pas la permission de supprimer cette station.')
                return redirect('stations_list')
            
            station_name = station.name
            station.delete()
            
            messages.success(request, f'La station "{station_name}" a été supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    
    return redirect('stations_list')
