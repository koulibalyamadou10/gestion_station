from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from pumps.models import Pump, PumpReading
from stations.models import StationManager
from permissions_web import manager_required

@login_required
@manager_required
def pumps_list_view(request):
    """
    Vue pour afficher la liste des pompes du gérant
    Accessible uniquement aux managers
    """
    # Récupérer la station assignée au manager
    try:
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager:
            messages.error(request, 'Aucune station ne vous est assignée.')
            return redirect('account:dashboard')
        
        station = station_manager.station
        
        # Récupérer toutes les pompes de cette station
        pumps = Pump.objects.filter(station=station).order_by('-created_at')
        
        # Filtres et recherche
        search_query = request.GET.get('search', '')
        type_filter = request.GET.get('type', '')
        
        # Appliquer les filtres
        if search_query:
            pumps = pumps.filter(
                Q(name__icontains=search_query)
            )
        
        if type_filter:
            pumps = pumps.filter(type=type_filter)
        
        # Statistiques
        total_pumps = Pump.objects.filter(station=station).count()
        essence_pumps = Pump.objects.filter(station=station, type='essence').count()
        gazole_pumps = Pump.objects.filter(station=station, type='gazole').count()
        filtered_count = pumps.count()
        
        context = {
            'pumps': pumps,
            'station': station,
            'total_pumps': total_pumps,
            'essence_pumps': essence_pumps,
            'gazole_pumps': gazole_pumps,
            'filtered_count': filtered_count,
            'search_query': search_query,
            'type_filter': type_filter,
        }
        
        return render(request, 'pumps/pumps_list.html', context)
    except Exception as e:
        messages.error(request, f'Erreur lors du chargement des pompes : {str(e)}')
        return redirect('account:dashboard')

@login_required
@manager_required
def create_pump_view(request):
    """
    Vue pour créer une nouvelle pompe
    Accessible uniquement aux managers
    """
    # Récupérer la station assignée au manager
    try:
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager:
            messages.error(request, 'Aucune station ne vous est assignée.')
            return redirect('pumps:pumps_list')
        
        station = station_manager.station
        
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            pump_type = request.POST.get('type', '').strip()
            initial_index = request.POST.get('initial_index', '').strip()
            current_index = request.POST.get('current_index', '').strip()
            
            # Validation
            if not name or not pump_type or not initial_index or not current_index:
                messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
                return redirect('pumps:pumps_list')
            
            try:
                initial_index_int = int(initial_index)
                current_index_int = int(current_index)
                
                # Créer la pompe
                pump = Pump.objects.create(
                    station=station,
                    name=name,
                    type=pump_type,
                    initial_index=initial_index_int,
                    current_index=current_index_int
                )
                
                messages.success(request, f'La pompe "{pump.name}" a été créée avec succès.')
                return redirect('pumps:pumps_list')
            except ValueError:
                messages.error(request, 'Les index doivent être des nombres entiers valides.')
                return redirect('pumps:pumps_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de la création de la pompe : {str(e)}')
        
        return redirect('pumps:pumps_list')
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')

@login_required
@manager_required
def pump_detail_view(request, pump_uuid):
    """
    Vue pour afficher les détails d'une pompe
    Accessible uniquement aux managers
    """
    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
        
        # Vérifier que la pompe appartient à la station du manager
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager or pump.station != station_manager.station:
            messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette pompe.')
            return redirect('pumps:pumps_list')
        
        # Récupérer les lectures de la pompe
        readings = PumpReading.objects.filter(pump=pump).order_by('-reading_date', '-created_at')[:10]
        
        # Calculer la quantité vendue totale
        quantity_sold_total = pump.current_index - pump.initial_index
        
        context = {
            'pump': pump,
            'readings': readings,
            'quantity_sold_total': quantity_sold_total,
        }
        
        return render(request, 'pumps/pump_detail.html', context)
    except Exception as e:
        messages.error(request, f'Erreur lors du chargement de la pompe : {str(e)}')
        return redirect('pumps:pumps_list')

@login_required
@manager_required
def update_pump_view(request, pump_uuid):
    """
    Vue pour modifier une pompe
    Accessible uniquement aux managers
    """
    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
        
        # Vérifier que la pompe appartient à la station du manager
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager or pump.station != station_manager.station:
            messages.error(request, 'Vous n\'avez pas la permission de modifier cette pompe.')
            return redirect('pumps:pumps_list')
        
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            pump_type = request.POST.get('type', '').strip()
            initial_index = request.POST.get('initial_index', '').strip()
            current_index = request.POST.get('current_index', '').strip()
            
            # Validation
            if not name or not pump_type or not initial_index or not current_index:
                messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
                return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
            
            try:
                initial_index_int = int(initial_index)
                current_index_int = int(current_index)
                
                # Mettre à jour la pompe
                pump.name = name
                pump.type = pump_type
                pump.initial_index = initial_index_int
                pump.current_index = current_index_int
                pump.save()
                
                messages.success(request, f'La pompe "{pump.name}" a été modifiée avec succès.')
                return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
            except ValueError:
                messages.error(request, 'Les index doivent être des nombres entiers valides.')
                return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
            except Exception as e:
                messages.error(request, f'Erreur lors de la modification de la pompe : {str(e)}')
        
        return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')

@login_required
@manager_required
def delete_pump_view(request, pump_uuid):
    """
    Vue pour supprimer une pompe
    Accessible uniquement aux managers
    """
    if request.method == 'POST':
        try:
            pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
            
            # Vérifier que la pompe appartient à la station du manager
            station_manager = StationManager.objects.filter(manager=request.user).first()
            if not station_manager or pump.station != station_manager.station:
                messages.error(request, 'Vous n\'avez pas la permission de supprimer cette pompe.')
                return redirect('pumps:pumps_list')
            
            pump_name = pump.name
            pump.delete()
            
            messages.success(request, f'La pompe "{pump_name}" a été supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression de la pompe : {str(e)}')
    
    return redirect('pumps:pumps_list')
