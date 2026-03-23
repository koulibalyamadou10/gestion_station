from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Max, Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from decimal import Decimal
from pumps.models import Pump, PumpReading
from stations.models import StationManager
from permissions_web import manager_required

@login_required
def pumps_list_view(request):
    """
    Vue pour afficher la liste des pompes
    Accessible aux managers (écriture) et aux admins (lecture seule)
    """
    try:
        # Pour les managers : récupérer leur station assignée
        if request.user.role == 'manager':
            station_manager = StationManager.objects.filter(manager=request.user).first()
            if not station_manager:
                messages.error(request, 'Aucune station ne vous est assignée.')
                return redirect('account:dashboard')
            station = station_manager.station
            stations = None  # Pas besoin pour les managers
            
            # Récupérer toutes les pompes de cette station
            base_pumps = Pump.objects.filter(station=station).select_related('station', 'station__city').order_by('-created_at')
            
            # Statistiques
            total_pumps = base_pumps.count()
            total_readings = PumpReading.objects.filter(pump__station=station).count()
            pumps_with_readings = PumpReading.objects.filter(pump__station=station).values('pump_id').distinct().count()
        # Pour les admins : récupérer toutes leurs stations et toutes leurs pompes
        elif request.user.role == 'admin':
            from stations.models import Station
            stations = Station.objects.filter(owner=request.user).order_by('name')
            if not stations.exists():
                messages.error(request, 'Vous n\'avez aucune station.')
                return redirect('account:dashboard')
            
            # Récupérer toutes les pompes de toutes les stations de l'admin
            base_pumps = Pump.objects.filter(station__in=stations).select_related('station', 'station__city').order_by('-created_at')
            
            # Statistiques pour toutes les stations
            total_pumps = base_pumps.count()
            total_readings = PumpReading.objects.filter(pump__station__in=stations).count()
            pumps_with_readings = PumpReading.objects.filter(pump__station__in=stations).values('pump_id').distinct().count()
            
            # Pour la compatibilité avec le template (affichage d'une station)
            station = stations.first() if stations else None
        else:
            messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
            return redirect('account:dashboard')
        
        # Filtres et recherche
        search_query = request.GET.get('search', '')
        station_filter = request.GET.get('station', '')
        pumps = base_pumps
        
        # Appliquer les filtres
        if search_query:
            pumps = pumps.filter(
                Q(name__icontains=search_query)
            )
        
        # Filtre par station (uniquement pour les admins)
        if request.user.role == 'admin' and station_filter:
            try:
                station_id = int(station_filter)
                pumps = pumps.filter(station_id=station_id)
            except ValueError:
                pass
        
        filtered_count = pumps.count()

        # Attacher la dernière lecture à chaque pompe pour l'affichage
        for pump in pumps:
            pump.latest_reading = pump.readings.order_by('-reading_date', '-created_at').first()
            pump.readings_count = pump.readings.count()
        
        context = {
            'pumps': pumps,
            'station': station,  # Pour compatibilité avec le template
            'stations': stations,  # Liste des stations pour les admins
            'total_pumps': total_pumps,
            'total_readings': total_readings,
            'pumps_with_readings': pumps_with_readings,
            'filtered_count': filtered_count,
            'search_query': search_query,
            'station_filter': station_filter,
            'is_read_only': request.user.role == 'admin',  # Lecture seule pour les admins
        }
        
        return render(request, 'pumps/pumps_list.html', context)
    except Exception as e:
        messages.error(request, f'Erreur lors du chargement des pompes : {str(e)}')
        return redirect('account:dashboard')

@login_required
def create_pump_view(request):
    """
    Vue pour créer une nouvelle pompe
    Accessible uniquement aux managers
    """
    # Création réservée à l'admin propriétaire
    try:
        if request.user.role != 'admin':
            messages.error(request, "Seul l'administrateur peut créer une pompe.")
            return redirect('pumps:pumps_list')

        from stations.models import Station
        stations = Station.objects.filter(owner=request.user).order_by('name')
        if not stations.exists():
            messages.error(request, "Vous n'avez aucune station.")
            return redirect('pumps:pumps_list')
        
        if request.method == 'POST':
            station_id = request.POST.get('station_id', '').strip()
            pump_type = request.POST.get('pump_type', '').strip().lower()
            pump_number = request.POST.get('pump_number', '').strip()
            initial_index = request.POST.get('initial_index', '').strip()
            current_index = request.POST.get('current_index', '').strip()
            
            # Validation
            if not station_id or not pump_type or not pump_number or not initial_index or not current_index:
                messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
                return redirect('pumps:pumps_list')
            
            try:
                station = stations.filter(id=station_id).first()
                if not station:
                    messages.error(request, "Station invalide pour cet administrateur.")
                    return redirect('pumps:pumps_list')

                if pump_type not in ('essence', 'gazoil'):
                    messages.error(request, "Type de pompe invalide. Choisissez Essence ou Gazoil.")
                    return redirect('pumps:pumps_list')

                pump_number_int = int(pump_number)
                if pump_number_int <= 0:
                    messages.error(request, "L'index de la pompe doit être supérieur à 0.")
                    return redirect('pumps:pumps_list')

                type_label = "Essence" if pump_type == "essence" else "Gazoil"
                name = f"Pompe {type_label} {pump_number_int}"

                # Empêcher les doublons du même nom sur la même station.
                if Pump.objects.filter(station=station, name__iexact=name).exists():
                    messages.error(request, f'La pompe "{name}" existe déjà pour cette station.')
                    return redirect('pumps:pumps_list')

                initial_index_decimal = Decimal(initial_index)
                current_index_decimal = Decimal(current_index)

                if current_index_decimal < initial_index_decimal:
                    messages.error(request, "L'index actuel doit être supérieur ou égal à l'index initial.")
                    return redirect('pumps:pumps_list')
                
                # Créer la pompe
                pump = Pump.objects.create(
                    station=station,
                    name=name,
                )

                # Créer la première lecture immédiatement
                PumpReading.objects.create(
                    pump=pump,
                    employee=None,
                    initial_index=initial_index_decimal,
                    current_index=current_index_decimal,
                    reading_date=timezone.now().date()
                )
                
                messages.success(request, f'La pompe "{pump.name}" a été créée avec sa première lecture.')
                return redirect('pumps:pumps_list')
            except ValueError:
                messages.error(request, 'Les index doivent être des nombres valides.')
                return redirect('pumps:pumps_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de la création de la pompe : {str(e)}')
        
        return redirect('pumps:pumps_list')
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')

@login_required
def pump_detail_view(request, pump_uuid):
    """
    Vue pour afficher les détails d'une pompe
    Accessible aux managers (écriture) et aux admins (lecture seule)
    """
    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
        
        # Vérifier les permissions selon le rôle
        if request.user.role == 'manager':
            # Pour les managers : vérifier que la pompe appartient à leur station
            station_manager = StationManager.objects.filter(manager=request.user).first()
            if not station_manager or pump.station != station_manager.station:
                messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette pompe.')
                return redirect('pumps:pumps_list')
        elif request.user.role == 'admin':
            # Pour les admins : vérifier que la pompe appartient à une de leurs stations
            if pump.station.owner != request.user:
                messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette pompe.')
                return redirect('pumps:pumps_list')
        else:
            messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
            return redirect('account:dashboard')
        
        readings_queryset = (
            PumpReading.objects
            .filter(pump=pump)
            .select_related('employee', 'employee__user')
            .annotate(
                quantity_sold=ExpressionWrapper(
                    F('current_index') - F('initial_index'),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .order_by('-reading_date', '-created_at')
        )

        date_filter = request.GET.get('reading_date', '').strip()
        employee_filter = request.GET.get('employee', '').strip()
        page_number = request.GET.get('page')

        if date_filter:
            readings_queryset = readings_queryset.filter(reading_date=date_filter)
        if employee_filter:
            readings_queryset = readings_queryset.filter(employee_id=employee_filter)

        paginator = Paginator(readings_queryset, 10)
        page_obj = paginator.get_page(page_number)

        total_aggregate = readings_queryset.aggregate(total=Sum('quantity_sold'))
        quantity_sold_total = total_aggregate['total'] or Decimal('0')
        latest_reading = PumpReading.objects.filter(pump=pump).order_by('-reading_date', '-created_at').first()
        employees = (
            pump.station.employee_set
            .select_related('user')
            .order_by('first_name', 'last_name')
        )
        
        context = {
            'pump': pump,
            'readings': page_obj.object_list,
            'page_obj': page_obj,
            'latest_reading': latest_reading,
            'employees': employees,
            'date_filter': date_filter,
            'employee_filter': employee_filter,
            'quantity_sold_total': quantity_sold_total,
            'is_read_only': request.user.role != 'admin',
            'can_create_pump': request.user.role == 'admin',
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
                return redirect('pumps:pump_detail', pump_id=pump_id)
            
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
                return redirect('pumps:pump_detail', pump_id=pump_id)
            except ValueError:
                messages.error(request, 'Les index doivent être des nombres entiers valides.')
                return redirect('pumps:pump_detail', pump_id=pump_id)
            except Exception as e:
                messages.error(request, f'Erreur lors de la modification de la pompe : {str(e)}')
        
        return redirect('pumps:pump_detail', pump_id=pump_id)
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')

@login_required
def delete_pump_view(request, pump_uuid):
    """
    Vue pour supprimer une pompe
    Accessible uniquement aux managers
    """
    if request.method == 'POST':
        try:
            pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
            
            # Permissions: admin propriétaire ou manager assigné à la station
            if request.user.role == 'admin':
                if pump.station.owner != request.user:
                    messages.error(request, "Vous n'avez pas la permission de supprimer cette pompe.")
                    return redirect('pumps:pumps_list')
            elif request.user.role == 'manager':
                station_manager = StationManager.objects.filter(manager=request.user).first()
                if not station_manager or pump.station != station_manager.station:
                    messages.error(request, "Vous n'avez pas la permission de supprimer cette pompe.")
                    return redirect('pumps:pumps_list')
            else:
                messages.error(request, "Vous n'avez pas la permission de supprimer cette pompe.")
                return redirect('pumps:pumps_list')

            readings_count = PumpReading.objects.filter(pump=pump).count()
            if readings_count > 1:
                messages.error(
                    request,
                    f'Suppression impossible: la pompe "{pump.name}" possède déjà {readings_count} lectures.'
                )
                return redirect('pumps:pumps_list')
            
            pump_name = pump.name
            pump.delete()
            
            messages.success(request, f'La pompe "{pump_name}" a été supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression de la pompe : {str(e)}')
    
    return redirect('pumps:pumps_list')

@login_required
@manager_required
def create_reading_view(request, pump_uuid):
    """
    Vue pour enregistrer une lecture de pompe
    Accessible uniquement aux managers
    Avec validations de sécurité et mise à jour du stock
    """
    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)
        
        # Vérifier que la pompe appartient à la station du manager
        station_manager = StationManager.objects.filter(manager=request.user).first()
        if not station_manager or pump.station != station_manager.station:
            messages.error(request, 'Vous n\'avez pas la permission d\'enregistrer une lecture pour cette pompe.')
            return redirect('pumps:pumps_list')
        
        if request.method == 'POST':
            previous_index = request.POST.get('previous_index', '').strip()
            current_index = request.POST.get('current_index', '').strip()
            reading_date = request.POST.get('reading_date', '').strip()
            
            # Validation des champs
            if not previous_index or not current_index or not reading_date:
                messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
                return redirect('pumps:pump_detail', pump_id=pump_id)
            
            try:
                previous_index_decimal = Decimal(previous_index)
                current_index_decimal = Decimal(current_index)
                
                # Validation 1: current_index doit être > previous_index
                if current_index_decimal <= previous_index_decimal:
                    messages.error(request, 'L\'index actuel doit être supérieur à l\'index précédent.')
                    return redirect('pumps:pump_detail', pump_id=pump_id)
                
                # Validation 2: reading_date doit être >= dernière date
                last_reading = PumpReading.objects.filter(pump=pump).aggregate(Max('reading_date'))
                if last_reading['reading_date__max']:
                    from datetime import datetime
                    last_date = last_reading['reading_date__max']
                    reading_date_obj = datetime.strptime(reading_date, '%Y-%m-%d').date()
                    
                    if reading_date_obj <= last_date:
                        messages.error(request, f'La date de lecture doit être postérieure à la dernière date enregistrée ({last_date.strftime("%d/%m/%Y")}).')
                        return redirect('pumps:pump_detail', pump_id=pump_id)
                
                # Validation 3: Une seule lecture par pompe par jour (optionnel mais conseillé)
                existing_reading = PumpReading.objects.filter(
                    pump=pump,
                    reading_date=reading_date
                ).first()
                
                if existing_reading:
                    messages.error(request, f'Une lecture existe déjà pour cette pompe à la date du {reading_date}.')
                    return redirect('pumps:pump_detail', pump_id=pump_id)
                
                # Calculer la quantité vendue
                quantity_sold = current_index_decimal - previous_index_decimal
                
                # Créer la lecture
                reading = PumpReading.objects.create(
                    pump=pump,
                    previous_index=previous_index_decimal,
                    current_index=current_index_decimal,
                    quantity_sold=quantity_sold,
                    reading_date=reading_date,
                    created_by=request.user
                )
                
                # Mettre à jour l'index actuel de la pompe
                pump.current_index = int(current_index_decimal)
                pump.save()
                
                # Mettre à jour le stock automatiquement
                from stocks.models import Stock
                stock, created = Stock.objects.get_or_create(
                    station=pump.station,
                    type=pump.type,
                    defaults={'quantity': Decimal('0')}
                )
                
                # Déduire la quantité vendue du stock
                if stock.quantity >= quantity_sold:
                    stock.quantity -= quantity_sold
                    stock.save()
                    messages.success(
                        request, 
                        f'Lecture enregistrée avec succès ! Quantité vendue : {quantity_sold} litres. '
                        f'Le stock a été mis à jour automatiquement.'
                    )
                else:
                    # Si le stock est insuffisant, on le met à 0 et on enregistre un avertissement
                    messages.warning(
                        request, 
                        f'Attention : Le stock de {pump.get_type_display()} est insuffisant. '
                        f'Quantité vendue : {quantity_sold}, Stock disponible : {stock.quantity}. '
                        f'Le stock a été mis à 0.'
                    )
                    stock.quantity = Decimal('0')
                    stock.save()
                
                return redirect('pumps:pump_detail', pump_id=pump_id)
                
            except ValueError as e:
                messages.error(request, 'Les index doivent être des nombres valides.')
                return redirect('pumps:pump_detail', pump_id=pump_id)
            except Exception as e:
                messages.error(request, f'Erreur lors de l\'enregistrement de la lecture : {str(e)}')
        
        return redirect('pumps:pump_detail', pump_id=pump_id)
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')
