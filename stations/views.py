from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
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
        return redirect('account:dashboard')
    
    # Récupérer toutes les stations pour les statistiques et filtres
    if request.user.role == 'super_admin':
        all_stations = Station.objects.select_related('city', 'owner').all()
    else:
        all_stations = Station.objects.select_related('city', 'owner').filter(owner=request.user)
    
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
            Q(city__name__icontains=search_query)
        )
    
    if city_filter:
        stations = stations.filter(city__name__icontains=city_filter)
    
    # Statistiques filtrées
    filtered_count = stations.count()
    
    # Liste des villes uniques pour le filtre
    if request.user.role == 'super_admin':
        cities = (
            Station.objects.exclude(city__isnull=True)
            .values_list('city__name', flat=True)
            .distinct()
            .order_by('city__name')
        )
    else:
        cities = (
            Station.objects.filter(owner=request.user)
            .exclude(city__isnull=True)
            .values_list('city__name', flat=True)
            .distinct()
            .order_by('city__name')
        )
    
    # Récupérer la liste des admins pour le super_admin
    admins = None
    managers = None
    if request.user.role == 'super_admin':
        from account.models import CustomUser
        admins = CustomUser.objects.filter(role='admin', is_active=True).order_by('first_name', 'last_name')
    elif request.user.role == 'admin':
        # Pour les admins, récupérer leurs gérants
        from account.models import CustomUser
        managers = CustomUser.objects.filter(role='manager', created_by=request.user, is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'stations': stations,
        'total_stations': total_stations,
        'filtered_count': filtered_count,
        'search_query': search_query,
        'city_filter': city_filter,
        'cities': cities,
        'admins': admins,
        'managers': managers,
    }
    
    return render(request, 'stations/stations_list.html', context)

@login_required
def get_managers_by_owner_view(request, owner_id):
    """
    Vue AJAX pour récupérer les gérants d'un propriétaire donné
    """
    if request.user.role not in ['super_admin', 'admin']:
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        from account.models import CustomUser
        owner = CustomUser.objects.get(id=owner_id, role='admin', is_active=True)
        
        # Vérifier les permissions
        if request.user.role == 'admin' and owner != request.user:
            return JsonResponse({'error': 'Permission refusée'}, status=403)
        
        # Récupérer les gérants de ce propriétaire
        managers = CustomUser.objects.filter(
            role='manager', 
            created_by=owner, 
            is_active=True
        ).order_by('first_name', 'last_name')
        
        managers_list = [
            {
                'id': manager.id,
                'name': manager.get_full_name(),
                'email': manager.email
            }
            for manager in managers
        ]
        
        return JsonResponse({'managers': managers_list}, status=200)
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Propriétaire introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def create_station_view(request):
    """
    Vue pour créer une nouvelle station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission de créer une station.')
        return redirect('stations:stations_list')
    
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
                return redirect('stations:stations_list')
            
            from account.models import CustomUser
            try:
                created_by = CustomUser.objects.get(id=created_by_id, role='admin', is_active=True)
            except CustomUser.DoesNotExist:
                messages.error(request, 'Le propriétaire sélectionné est invalide.')
                return redirect('stations:stations_list')
        else:
            # L'admin crée pour lui-même
            created_by = request.user
        
        # Validation
        if not name or not city or not address:
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
            return redirect('stations:stations_list')
        
        if not latitude or not longitude:
            messages.error(request, 'Veuillez sélectionner un emplacement sur la carte.')
            return redirect('stations:stations_list')
        
        try:
            # Convertir les coordonnées en Decimal
            from decimal import Decimal
            latitude_decimal = Decimal(latitude)
            longitude_decimal = Decimal(longitude)
            
            # Récupérer le manager sélectionné
            manager_id = request.POST.get('manager', '').strip()
            if not manager_id:
                messages.error(request, 'Veuillez sélectionner un gérant pour la station.')
                return redirect('stations:stations_list')
            
            from account.models import CustomUser
            try:
                manager = CustomUser.objects.get(id=manager_id, role='manager', is_active=True)
                # Vérifier que le manager appartient bien au propriétaire
                if manager.created_by != created_by:
                    messages.error(request, 'Le gérant sélectionné n\'appartient pas au propriétaire choisi.')
                    return redirect('stations:stations_list')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Le gérant sélectionné est invalide.')
                return redirect('stations:stations_list')
            
            # Créer la station
            station = Station.objects.create(
                name=name,
                city=city,
                address=address,
                latitude=latitude_decimal,
                longitude=longitude_decimal,
                created_by=created_by
            )
            
            # Créer la relation StationManager
            from stations.models import StationManager
            StationManager.objects.create(
                station=station,
                manager=manager
            )
            
            messages.success(request, f'La station "{station.name}" a été créée avec succès.')
            return redirect('stations:stations_list')
        except ValueError:
            messages.error(request, 'Les coordonnées géographiques sont invalides.')
            return redirect('stations:stations_list')
        except Exception as e:
            messages.error(request, f'Erreur lors de la création de la station : {str(e)}')
    
    return redirect('stations:stations_list')

@login_required
def station_detail_view(request, station_uuid):
    """
    Vue pour afficher les détails d'une station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
        return redirect('account:dashboard')
    
    try:
        station = get_object_or_404(Station, station_uuid=station_uuid)
        
        # Vérifier les permissions
        if request.user.role == 'admin' and station.created_by != request.user:
            messages.error(request, 'Vous n\'avez pas la permission de voir cette station.')
            return redirect('stations:stations_list')
        
        # Récupérer le gérant actuel de la station
        current_manager = None
        try:
            from stations.models import StationManager
            station_manager = StationManager.objects.filter(station=station).first()
            if station_manager:
                current_manager = station_manager.manager
        except:
            pass
        
        # Récupérer la liste des admins pour le super_admin
        admins = None
        managers = None
        if request.user.role == 'super_admin':
            from account.models import CustomUser
            admins = CustomUser.objects.filter(role='admin', is_active=True).order_by('first_name', 'last_name')
        elif request.user.role == 'admin':
            # Pour les admins, récupérer leurs gérants
            from account.models import CustomUser
            managers = CustomUser.objects.filter(role='manager', created_by=request.user, is_active=True).order_by('first_name', 'last_name')
        
        context = {
            'station': station,
            'current_manager': current_manager,
            'admins': admins,
            'managers': managers,
        }
        
        return render(request, 'stations/stations_detail.html', context)
    except Exception as e:
        messages.error(request, f'Erreur lors du chargement de la station : {str(e)}')
        return redirect('stations:stations_list')

@login_required
def update_station_view(request, station_uuid):
    """
    Vue pour modifier une station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission de modifier une station.')
        return redirect('stations:stations_list')
    
    if request.method == 'POST':
        try:
            station = get_object_or_404(Station, station_uuid=station_uuid)
            
            # Vérifier les permissions
            if request.user.role == 'admin' and station.created_by != request.user:
                messages.error(request, 'Vous n\'avez pas la permission de modifier cette station.')
                return redirect('stations:stations_list')
            
            name = request.POST.get('name', '').strip()
            city = request.POST.get('city', '').strip()
            address = request.POST.get('address', '').strip()
            latitude = request.POST.get('latitude', '').strip()
            longitude = request.POST.get('longitude', '').strip()
            
            # Validation
            if not name or not city or not address:
                messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
                return redirect('stations:station_detail', station_uuid=station_uuid)
            
            if not latitude or not longitude:
                messages.error(request, 'Veuillez sélectionner un emplacement sur la carte.')
                return redirect('stations:station_detail', station_uuid=station_uuid)
            
            # Déterminer le created_by selon le rôle (seulement si super_admin)
            if request.user.role == 'super_admin':
                created_by_id = request.POST.get('created_by', '').strip()
                if created_by_id:
                    from account.models import CustomUser
                    try:
                        created_by = CustomUser.objects.get(id=created_by_id, role='admin', is_active=True)
                        station.created_by = created_by
                    except CustomUser.DoesNotExist:
                        pass  # Garder le created_by actuel si invalide
            
            # Gérer le changement de gérant
            manager_id = request.POST.get('manager', '').strip()
            if manager_id:
                from account.models import CustomUser
                try:
                    new_manager = CustomUser.objects.get(id=manager_id, role='manager', is_active=True)
                    # Vérifier que le manager appartient bien au propriétaire
                    if new_manager.created_by != station.created_by:
                        messages.error(request, 'Le gérant sélectionné n\'appartient pas au propriétaire de la station.')
                        return redirect('stations:station_detail', station_uuid=station_uuid)
                    
                    # Mettre à jour ou créer la relation StationManager
                    from stations.models import StationManager
                    station_manager, created = StationManager.objects.get_or_create(
                        station=station,
                        defaults={'manager': new_manager}
                    )
                    if not created:
                        station_manager.manager = new_manager
                        station_manager.save()
                except CustomUser.DoesNotExist:
                    messages.error(request, 'Le gérant sélectionné est invalide.')
                    return redirect('stations:station_detail', station_uuid=station_uuid)
            
            # Convertir les coordonnées en Decimal
            from decimal import Decimal
            latitude_decimal = Decimal(latitude)
            longitude_decimal = Decimal(longitude)
            
            # Mettre à jour la station
            station.name = name
            station.city = city
            station.address = address
            station.latitude = latitude_decimal
            station.longitude = longitude_decimal
            station.save()
            
            messages.success(request, f'La station "{station.name}" a été modifiée avec succès.')
            return redirect('stations:station_detail', station_uuid=station_uuid)
        except ValueError:
            messages.error(request, 'Les coordonnées géographiques sont invalides.')
            return redirect('stations:station_detail', station_uuid=station_uuid)
        except Exception as e:
            messages.error(request, f'Erreur lors de la modification : {str(e)}')
            return redirect('stations:station_detail', station_uuid=station_uuid)
    
    return redirect('stations:stations_list')

@login_required
def delete_station_view(request, station_uuid):
    """
    Vue pour supprimer une station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission de supprimer une station.')
        return redirect('stations:stations_list')
    
    if request.method == 'POST':
        try:
            station = get_object_or_404(Station, station_uuid=station_uuid)
            
            # Vérifier les permissions
            if request.user.role == 'admin' and station.created_by != request.user:
                messages.error(request, 'Vous n\'avez pas la permission de supprimer cette station.')
                return redirect('stations:stations_list')
            
            station_name = station.name
            station.delete()
            
            messages.success(request, f'La station "{station_name}" a été supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    
    return redirect('stations:stations_list')

@login_required
def assign_manager_view(request, station_uuid):
    """
    Vue pour assigner ou changer le gérant d'une station
    Accessible aux admins et super_admins
    """
    if request.user.role not in ['super_admin', 'admin']:
        messages.error(request, 'Vous n\'avez pas la permission d\'assigner un gérant.')
        return redirect('account:dashboard')
    
    if request.method == 'POST':
        try:
            station = get_object_or_404(Station, station_uuid=station_uuid)
            
            # Vérifier les permissions
            if request.user.role == 'admin' and station.created_by != request.user:
                messages.error(request, 'Vous n\'avez pas la permission d\'assigner un gérant à cette station.')
                return redirect('stations:station_detail', station_uuid=station_uuid)
            
            # Si super_admin, permettre de changer le propriétaire
            owner_id = None
            if request.user.role == 'super_admin':
                owner_id = request.POST.get('owner', '').strip()
                if owner_id:
                    from account.models import CustomUser
                    try:
                        new_owner = CustomUser.objects.get(id=owner_id, role='admin', is_active=True)
                        station.created_by = new_owner
                        station.save()
                    except CustomUser.DoesNotExist:
                        pass  # Garder le propriétaire actuel si invalide
            
            manager_id = request.POST.get('manager', '').strip()
            
            if not manager_id:
                messages.error(request, 'Veuillez sélectionner un gérant.')
                return redirect('stations:station_detail', station_uuid=station_uuid)
            
            from account.models import CustomUser
            try:
                new_manager = CustomUser.objects.get(id=manager_id, role='manager', is_active=True)
                # Vérifier que le manager appartient bien au propriétaire de la station
                if new_manager.created_by != station.created_by:
                    messages.error(request, 'Le gérant sélectionné n\'appartient pas au propriétaire de la station.')
                    return redirect('stations:station_detail', station_uuid=station_uuid)
                
                # Mettre à jour ou créer la relation StationManager
                from stations.models import StationManager
                station_manager, created = StationManager.objects.get_or_create(
                    station=station,
                    defaults={'manager': new_manager}
                )
                if not created:
                    station_manager.manager = new_manager
                    station_manager.save()
                
                messages.success(request, f'Le gérant "{new_manager.get_full_name}" a été assigné à la station "{station.name}" avec succès.')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Le gérant sélectionné est invalide.')
            except Exception as e:
                messages.error(request, f'Erreur lors de l\'assignation du gérant : {str(e)}')
        except Exception as e:
            messages.error(request, f'Erreur : {str(e)}')
    
    return redirect('stations:station_detail', station_uuid=station_uuid)
