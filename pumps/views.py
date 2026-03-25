from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from decimal import Decimal, InvalidOperation
import json
from pumps.models import Pump, PumpReading, PumpReset
from sale.models import Sale
from employee.models import Employee
from inventory.models import Inventory
from stations.models import Station, StationManager
from wallet.models import Account
from daily_stock.models import DailyStock
from permissions_web import manager_required


def _previous_reading_strictly_before(reading):
    """Lecture immédiatement précédente (même pompe), pour calculer le volume vendu."""
    return (
        PumpReading.objects.filter(pump_id=reading.pump_id)
        .exclude(pk=reading.pk)
        .filter(
            Q(reading_date__lt=reading.reading_date)
            | Q(reading_date=reading.reading_date, created_at__lt=reading.created_at)
            | Q(
                reading_date=reading.reading_date,
                created_at=reading.created_at,
                id__lt=reading.id,
            )
        )
        .order_by("-reading_date", "-created_at", "-id")
        .first()
    )


def _quantity_sold_for_reading(reading):
    """Volume vendu sur une lecture : écart avec la lecture précédente ; 0 pour la première chronologique."""
    prev = _previous_reading_strictly_before(reading)
    if prev is None:
        return Decimal("0")
    qty = reading.current_index - prev.current_index
    return qty if qty > 0 else Decimal("0")


def _create_sale_from_reading(reading, recorded_by):
    """
    Crée automatiquement une vente à partir d'une lecture de pompe.
    Le type de produit est déduit du nom de la pompe.
    """
    qty = _quantity_sold_for_reading(reading)

    pump_name = (reading.pump.name or "").lower()
    is_essence = "essence" in pump_name

    unit_price_essence = Decimal(str(getattr(settings, "PRODUCT_PRICE_ESSENCE", 0)))
    unit_price_diesel = Decimal(str(getattr(settings, "PRODUCT_PRICE_DIESEL", 0)))

    qty_gasoline = qty if is_essence else Decimal("0")
    qty_diesel = qty if not is_essence else Decimal("0")

    total_amount = (qty_gasoline * unit_price_essence) + (qty_diesel * unit_price_diesel)

    return Sale.objects.create(
        station=reading.pump.station,
        pump_reading=reading,
        sale_date=reading.reading_date,
        qty_gasoline=qty_gasoline,
        qty_diesel=qty_diesel,
        unit_price_gasoline=unit_price_essence,
        unit_price_diesel=unit_price_diesel,
        total_amount=total_amount,
        recorded_by=recorded_by,
    )


def _trace_daily_stock_from_sale(sale, recorded_by):
    """
    Cumule les volumes essence / gazoil vendus dans DailyStock (par station et date).
    Un enregistrement par (station, stock_date) : les qtés = cumul des litres vendus ce jour-là.
    """
    inc_gas = sale.qty_gasoline or Decimal("0")
    inc_die = sale.qty_diesel or Decimal("0")
    if inc_gas == 0 and inc_die == 0:
        return

    ds, created = DailyStock.objects.get_or_create(
        station=sale.station,
        stock_date=sale.sale_date,
        defaults={
            "recorded_by": recorded_by,
            "qty_gasoline": inc_gas,
            "qty_diesel": inc_die,
        },
    )
    if not created:
        ds.qty_gasoline = (ds.qty_gasoline or Decimal("0")) + inc_gas
        ds.qty_diesel = (ds.qty_diesel or Decimal("0")) + inc_die
        ds.recorded_by = recorded_by
        ds.save(update_fields=["qty_gasoline", "qty_diesel", "recorded_by", "updated_at"])


def _record_inventory_out_and_decrease_station_stock(sale):
    """
    Insère une ligne Inventory (sorties en litres négatifs) et diminue stock sur la station.
    Les entrées (livraisons, initial) restent positives : la somme des lignes = historique net des cuves.
    """
    inc_gas = sale.qty_gasoline or Decimal("0")
    inc_die = sale.qty_diesel or Decimal("0")
    if inc_gas == 0 and inc_die == 0:
        return

    Inventory.objects.create(
        station_id=sale.station_id,
        qty_gasoline=-inc_gas,
        qty_diesel=-inc_die,
    )
    station = Station.objects.select_for_update().get(pk=sale.station_id)
    station.stock_gasoline = (station.stock_gasoline or Decimal("0")) - inc_gas
    station.stock_diesel = (station.stock_diesel or Decimal("0")) - inc_die
    station.save(update_fields=["stock_gasoline", "stock_diesel", "updated_at"])


def _compute_sale_total_for_pump_reading(pump, previous_current_index, new_current_index):
    """Montant de vente (GNF) pour une lecture, sans créer d'objet en base."""
    qty = new_current_index - previous_current_index
    if qty < 0:
        qty = Decimal("0")
    pump_name = (pump.name or "").lower()
    is_essence = "essence" in pump_name
    unit_price_essence = Decimal(str(getattr(settings, "PRODUCT_PRICE_ESSENCE", 0)))
    unit_price_diesel = Decimal(str(getattr(settings, "PRODUCT_PRICE_DIESEL", 0)))
    qty_gasoline = qty if is_essence else Decimal("0")
    qty_diesel = qty if not is_essence else Decimal("0")
    return (qty_gasoline * unit_price_essence) + (qty_diesel * unit_price_diesel)


def _parse_and_validate_wallet_allocations(
    request, allocations_json, station_wallets, total_expected
):
    """
    Retourne (dict wallet_uuid -> Decimal, None) ou (None, redirect_response).
    total_expected : Decimal
    """
    allocations = []
    if allocations_json:
        try:
            parsed = json.loads(allocations_json)
            if isinstance(parsed, list):
                allocations = parsed
        except json.JSONDecodeError:
            allocations = []

    allocations_by_uuid = {}
    for item in allocations:
        wallet_uuid = str(item.get("wallet_uuid", "")).strip()
        amount_raw = str(item.get("amount", "")).strip()
        if not wallet_uuid:
            continue
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Montant wallet invalide.")
            return None, redirect("pumps:bulk_pump_reading")

        if amount < 0:
            messages.error(request, "Les montants wallet ne peuvent pas être négatifs.")
            return None, redirect("pumps:bulk_pump_reading")
        allocations_by_uuid[wallet_uuid] = allocations_by_uuid.get(wallet_uuid, Decimal("0")) + amount

    if not allocations_by_uuid and len(station_wallets) == 1:
        allocations_by_uuid[str(station_wallets[0].uuid)] = total_expected

    if not allocations_by_uuid:
        messages.error(request, "Veuillez répartir le montant dans au moins un wallet.")
        return None, redirect("pumps:bulk_pump_reading")

    valid_wallets_map = {str(w.uuid): w for w in station_wallets}
    for wallet_uuid in allocations_by_uuid.keys():
        if wallet_uuid not in valid_wallets_map:
            messages.error(request, "Un wallet sélectionné est invalide pour cette station.")
            return None, redirect("pumps:bulk_pump_reading")

    allocated_sum = sum(allocations_by_uuid.values(), Decimal("0"))
    if allocated_sum.quantize(Decimal("0.01")) != total_expected.quantize(Decimal("0.01")):
        messages.error(
            request,
            "La somme répartie dans les wallets doit être égale au montant total des ventes.",
        )
        return None, redirect("pumps:bulk_pump_reading")

    return allocations_by_uuid, None


def _redirect_after_pump_form(request):
    """Redirige vers `next` (POST) si URL interne autorisée, sinon vers la liste des pompes."""
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("pumps:pumps_list")


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
        
        station_wallets = {}
        station_scope_for_wallets = [station] if request.user.role == "manager" and station else stations
        if station_scope_for_wallets:
            wallets_qs = (
                Account.objects
                .filter(station__in=station_scope_for_wallets)
                .select_related("station")
                .order_by("name")
            )
            for wallet in wallets_qs:
                station_key = str(wallet.station_id)
                station_wallets.setdefault(station_key, []).append({
                    "uuid": str(wallet.uuid),
                    "name": wallet.name,
                    "currency": wallet.currency,
                    "balance": str(wallet.balance),
                })

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
            'station_wallets': station_wallets,
            'product_price_essence': Decimal(str(getattr(settings, "PRODUCT_PRICE_ESSENCE", 0))),
            'product_price_diesel': Decimal(str(getattr(settings, "PRODUCT_PRICE_DIESEL", 0))),
        }
        
        return render(request, 'pumps/pumps_list.html', context)
    except Exception as e:
        messages.error(request, f'Erreur lors du chargement des pompes : {str(e)}')
        return redirect('account:dashboard')

@login_required
def create_pump_view(request):
    """
    Création d'une pompe (admin propriétaire ou super_admin).
    Redirection après succès/erreur : paramètre POST `next` (URL du même site) ou liste des pompes.
    """
    from stations.models import Station

    try:
        if request.user.role not in ("admin", "super_admin"):
            messages.error(request, "Seul l'administrateur peut créer une pompe.")
            return redirect("pumps:pumps_list")

        if request.user.role == "admin":
            owned_stations = Station.objects.filter(owner=request.user).order_by("name")
            if not owned_stations.exists():
                messages.error(request, "Vous n'avez aucune station.")
                return redirect("pumps:pumps_list")
        else:
            owned_stations = Station.objects.all().order_by("name")
            if not owned_stations.exists():
                messages.error(request, "Aucune station en base.")
                return redirect("pumps:pumps_list")

        if request.method != "POST":
            return redirect("pumps:pumps_list")

        station_id = request.POST.get("station_id", "").strip()
        pump_type = request.POST.get("pump_type", "").strip().lower()
        pump_number = request.POST.get("pump_number", "").strip()
        current_index = request.POST.get("current_index", "").strip()

        if not station_id or not pump_type or not pump_number or not current_index:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            return _redirect_after_pump_form(request)

        try:
            if request.user.role == "admin":
                station = owned_stations.filter(id=station_id).first()
            else:
                station = Station.objects.filter(id=station_id).first()

            if not station:
                messages.error(request, "Station invalide pour cet utilisateur.")
                return _redirect_after_pump_form(request)

            if pump_type not in ("essence", "gazoil"):
                messages.error(request, "Type de pompe invalide. Choisissez Essence ou Gazoil.")
                return _redirect_after_pump_form(request)

            pump_number_int = int(pump_number)
            if pump_number_int <= 0:
                messages.error(request, "L'index de la pompe doit être supérieur à 0.")
                return _redirect_after_pump_form(request)

            type_label = "Essence" if pump_type == "essence" else "Gazoil"
            name = f"Pompe {pump_number_int} / {type_label}"

            if Pump.objects.filter(station=station, name__iexact=name).exists():
                messages.error(request, f'La pompe "{name}" existe déjà pour cette station.')
                return _redirect_after_pump_form(request)

            current_index_decimal = Decimal(current_index)
            if current_index_decimal < 0:
                messages.error(request, "L'index compteur doit être positif ou nul.")
                return _redirect_after_pump_form(request)

            pump = Pump.objects.create(
                station=station,
                name=name,
            )

            PumpReading.objects.create(
                pump=pump,
                employee=None,
                current_index=current_index_decimal,
                reading_date=timezone.now().date(),
            )

            messages.success(request, f'La pompe "{pump.name}" a été créée avec sa première lecture.')
            return _redirect_after_pump_form(request)
        except ValueError:
            messages.error(request, "Les index doivent être des nombres valides.")
            return _redirect_after_pump_form(request)
        except Exception as e:
            messages.error(request, f"Erreur lors de la création de la pompe : {str(e)}")
            return _redirect_after_pump_form(request)
    except Exception as e:
        messages.error(request, f"Erreur : {str(e)}")
        return redirect("pumps:pumps_list")

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
        elif request.user.role == 'super_admin':
            pass
        else:
            messages.error(request, 'Vous n\'avez pas la permission d\'accéder à cette page.')
            return redirect('account:dashboard')
        
        readings_base = (
            PumpReading.objects.filter(pump=pump).select_related("employee", "employee__user")
        )

        date_filter = request.GET.get('reading_date', '').strip()
        employee_filter = request.GET.get('employee', '').strip()
        page_number = request.GET.get('page')
        reset_page_number = request.GET.get('reset_page')

        # Un manager doit pouvoir voir toutes les lectures de la pompe (station déjà contrôlée plus haut)

        if date_filter:
            readings_base = readings_base.filter(reading_date=date_filter)
        if employee_filter:
            readings_base = readings_base.filter(employee_id=employee_filter)

        readings_chrono = list(readings_base.order_by("reading_date", "created_at", "id"))
        prev_c = None
        quantity_sold_total = Decimal("0")
        for r in readings_chrono:
            if prev_c is not None:
                q = r.current_index - prev_c
                if q > 0:
                    quantity_sold_total += q
            prev_c = r.current_index

        readings_queryset = readings_base.order_by("-reading_date", "-created_at")
        paginator = Paginator(readings_queryset, 10)
        page_obj = paginator.get_page(page_number)

        for r in page_obj.object_list:
            r.quantity_sold = _quantity_sold_for_reading(r)
        latest_reading = PumpReading.objects.filter(pump=pump).order_by('-reading_date', '-created_at').first()
        employees = (
            pump.station.employee_set
            .select_related('user')
            .order_by('first_name', 'last_name')
        )

        reset_page_obj = None
        reset_history = []
        if request.user.role in ('admin', 'super_admin', 'manager'):
            reset_queryset = PumpReset.objects.filter(pump=pump).select_related('reset_by').order_by('-created_at')
            reset_paginator = Paginator(reset_queryset, 10)
            reset_page_obj = reset_paginator.get_page(reset_page_number)
            reset_history = reset_page_obj.object_list
        
        context = {
            'pump': pump,
            'readings': page_obj.object_list,
            'page_obj': page_obj,
            'latest_reading': latest_reading,
            'employees': employees,
            'date_filter': date_filter,
            'employee_filter': employee_filter,
            'quantity_sold_total': quantity_sold_total,
            'reset_history': reset_history,
            'reset_page_obj': reset_page_obj,
            'is_read_only': request.user.role not in ('admin', 'super_admin'),
            'can_create_pump': request.user.role in ('admin', 'super_admin'),
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

            if not name:
                messages.error(request, 'Veuillez remplir le nom de la pompe.')
                return redirect('pumps:pump_detail', pump_uuid=pump_uuid)

            try:
                pump.name = name
                pump.save(update_fields=['name', 'updated_at'])

                messages.success(request, f'La pompe "{pump.name}" a été modifiée avec succès.')
                return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
            except Exception as e:
                messages.error(request, f'Erreur lors de la modification de la pompe : {str(e)}')
        
        return redirect('pumps:pump_detail', pump_uuid=pump_uuid)
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
                    return _redirect_after_pump_form(request)
            elif request.user.role == 'super_admin':
                pass
            elif request.user.role == 'manager':
                station_manager = StationManager.objects.filter(manager=request.user).first()
                if not station_manager or pump.station != station_manager.station:
                    messages.error(request, "Vous n'avez pas la permission de supprimer cette pompe.")
                    return _redirect_after_pump_form(request)
            else:
                messages.error(request, "Vous n'avez pas la permission de supprimer cette pompe.")
                return _redirect_after_pump_form(request)

            readings_count = PumpReading.objects.filter(pump=pump).count()
            if readings_count > 1:
                messages.error(
                    request,
                    f'Suppression impossible: la pompe "{pump.name}" possède déjà {readings_count} lectures.'
                )
                return _redirect_after_pump_form(request)
            
            pump_name = pump.name
            pump.delete()
            
            messages.success(request, f'La pompe "{pump_name}" a été supprimée avec succès.')
            return _redirect_after_pump_form(request)
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression de la pompe : {str(e)}')
            return _redirect_after_pump_form(request)
    
    return redirect('pumps:pumps_list')

@login_required
def create_reading_view(request, pump_uuid):
    """
    Enregistrement d'une lecture : gérant de la station, ou admin propriétaire, ou super_admin.
    """
    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)

        allowed = False
        if request.user.role == 'manager':
            station_manager = StationManager.objects.filter(manager=request.user).first()
            allowed = bool(station_manager and pump.station_id == station_manager.station_id)
        elif request.user.role == 'admin':
            allowed = pump.station.owner_id == request.user.id
        elif request.user.role == 'super_admin':
            allowed = True
        if not allowed:
            messages.error(request, 'Vous n\'avez pas la permission d\'enregistrer une lecture pour cette pompe.')
            return redirect('pumps:pumps_list')
        
        if request.method == 'POST':
            current_index = request.POST.get('current_index', '').strip()
            allocations_json = request.POST.get('wallet_allocations', '').strip()
            today = timezone.now().date()
            
            # Validation des champs
            if not current_index:
                messages.error(request, 'Veuillez renseigner l\'index compteur.')
                return redirect('pumps:pumps_list')
            
            try:
                current_index_decimal = Decimal(current_index)

                latest_before = (
                    PumpReading.objects.filter(pump=pump)
                    .order_by("-reading_date", "-created_at", "-id")
                    .first()
                )
                previous_current = latest_before.current_index if latest_before else Decimal("0")

                if current_index_decimal <= previous_current:
                    messages.error(request, 'L\'index actuel doit être supérieur à l\'index de la dernière lecture.')
                    return redirect('pumps:pumps_list')
                
                # Validation 2: une seule lecture/jour/pompe
                # seulement quand la pompe a deja plus d'une lecture.
                readings_count = PumpReading.objects.filter(pump=pump).count()
                existing_reading = PumpReading.objects.filter(
                    pump=pump,
                    reading_date=today
                ).first()
                
                if readings_count > 1 and existing_reading:
                    messages.error(request, 'Une lecture a déjà été enregistrée aujourd\'hui pour cette pompe.')
                    return redirect('pumps:pumps_list')
                
                employee = Employee.objects.filter(user=request.user, station=pump.station).first()
                station_wallets = list(Account.objects.filter(station=pump.station).order_by("name"))
                if not station_wallets:
                    messages.error(
                        request,
                        "Aucun wallet n'est configuré pour cette station. Veuillez créer au moins un wallet."
                    )
                    return redirect('pumps:pumps_list')

                with transaction.atomic():
                    # Créer la lecture
                    reading = PumpReading.objects.create(
                        pump=pump,
                        employee=employee,
                        current_index=current_index_decimal,
                        reading_date=today,
                    )
                    sale = _create_sale_from_reading(reading, request.user)
                    _trace_daily_stock_from_sale(sale, request.user)
                    _record_inventory_out_and_decrease_station_stock(sale)
                    total_amount = sale.total_amount or Decimal("0")

                    allocations = []
                    if allocations_json:
                        try:
                            parsed = json.loads(allocations_json)
                            if isinstance(parsed, list):
                                allocations = parsed
                        except json.JSONDecodeError:
                            allocations = []

                    allocations_by_uuid = {}
                    for item in allocations:
                        wallet_uuid = str(item.get("wallet_uuid", "")).strip()
                        amount_raw = str(item.get("amount", "")).strip()
                        if not wallet_uuid:
                            continue
                        try:
                            amount = Decimal(amount_raw)
                        except (InvalidOperation, ValueError):
                            messages.error(request, "Montant wallet invalide.")
                            return redirect('pumps:pumps_list')

                        if amount < 0:
                            messages.error(request, "Les montants wallet ne peuvent pas être négatifs.")
                            return redirect('pumps:pumps_list')
                        allocations_by_uuid[wallet_uuid] = allocations_by_uuid.get(wallet_uuid, Decimal("0")) + amount

                    if total_amount > 0:
                        # Auto-répartition si un seul wallet et aucune allocation envoyée
                        if not allocations_by_uuid and len(station_wallets) == 1:
                            allocations_by_uuid[str(station_wallets[0].uuid)] = total_amount

                        if not allocations_by_uuid:
                            messages.error(
                                request,
                                "Veuillez répartir le montant de la vente dans au moins un wallet.",
                            )
                            return redirect("pumps:pumps_list")

                        valid_wallets_map = {str(w.uuid): w for w in station_wallets}
                        for wallet_uuid in allocations_by_uuid.keys():
                            if wallet_uuid not in valid_wallets_map:
                                messages.error(
                                    request,
                                    "Un wallet sélectionné est invalide pour cette station.",
                                )
                                return redirect("pumps:pumps_list")

                        allocated_sum = sum(allocations_by_uuid.values(), Decimal("0"))
                        if allocated_sum.quantize(Decimal("0.01")) != total_amount.quantize(Decimal("0.01")):
                            messages.error(
                                request,
                                "La somme répartie dans les wallets doit être égale au montant total de la vente.",
                            )
                            return redirect("pumps:pumps_list")

                        for wallet_uuid, amount in allocations_by_uuid.items():
                            if amount <= 0:
                                continue
                            wallet = valid_wallets_map[wallet_uuid]
                            wallet.balance = (wallet.balance or Decimal("0")) + amount
                            wallet.save(update_fields=["balance", "updated_at"])

                messages.success(request, 'Lecture enregistrée avec succès.')
                return redirect('pumps:pumps_list')
                
            except ValueError:
                messages.error(request, 'Les index doivent être des nombres valides.')
                return redirect('pumps:pumps_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de l\'enregistrement de la lecture : {str(e)}')
        
        return redirect('pumps:pumps_list')
    except Exception as e:
        messages.error(request, f'Erreur : {str(e)}')
        return redirect('pumps:pumps_list')


@login_required
def bulk_pump_reading_view(request):
    """
    Saisie groupée des lectures pour une station.
    Gérant : sa station assignée. Admin : station_uuid (query/POST) ou station unique possédée.
    Super_admin : station_uuid obligatoire.
    """
    station = None
    bulk_station_uuid_for_form = None

    if request.user.role == "manager":
        station_manager = StationManager.objects.filter(manager=request.user).select_related("station").first()
        if not station_manager:
            messages.error(request, "Aucune station ne vous est assignée.")
            return redirect("account:dashboard")
        station = station_manager.station
    elif request.user.role == "admin":
        owned = Station.objects.filter(owner=request.user)
        station_uuid = (request.GET.get("station_uuid") or request.POST.get("station_uuid") or "").strip()
        if station_uuid:
            station = owned.filter(station_uuid=station_uuid).first()
        elif owned.count() == 1:
            station = owned.first()
        if station:
            bulk_station_uuid_for_form = str(station.station_uuid)
        else:
            messages.error(
                request,
                "Pour la saisie groupée, ouvrez cette page depuis la fiche de l'une de vos stations "
                "(ou ajoutez ?station_uuid=… à l'URL).",
            )
            return redirect("stations:stations_list")
    elif request.user.role == "super_admin":
        station_uuid = (request.GET.get("station_uuid") or request.POST.get("station_uuid") or "").strip()
        if station_uuid:
            station = Station.objects.filter(station_uuid=station_uuid).first()
        if not station:
            messages.error(
                request,
                "Pour la saisie groupée, ouvrez cette page depuis la fiche d'une station "
                "(paramètre station_uuid).",
            )
            return redirect("stations:stations_list")
        bulk_station_uuid_for_form = str(station.station_uuid)
    else:
        messages.error(request, "Accès refusé.")
        return redirect("account:dashboard")
    pumps_qs = (
        Pump.objects.filter(station=station)
        .select_related("station")
        .order_by("name")
    )
    station_wallets_list = list(
        Account.objects.filter(station=station, uuid__isnull=False).order_by("name")
    )

    pumps_data = []
    for p in pumps_qs:
        if not p.pump_uuid:
            continue
        lr = p.readings.order_by("-reading_date", "-created_at").first()
        prev = lr.current_index if lr else Decimal("0")
        pumps_data.append(
            {
                "pump_uuid": str(p.pump_uuid),
                "name": p.name,
                "previous_index": str(prev),
            }
        )

    if request.method == "POST":
        readings_json = request.POST.get("readings_json", "").strip()
        allocations_json = request.POST.get("wallet_allocations", "").strip()
        today = timezone.now().date()

        try:
            readings_data = json.loads(readings_json) if readings_json else []
        except json.JSONDecodeError:
            messages.error(request, "Données de lecture invalides.")
            return redirect("pumps:bulk_pump_reading")

        if not isinstance(readings_data, list) or not readings_data:
            messages.error(request, "Ajoutez au moins une lecture de pompe.")
            return redirect("pumps:bulk_pump_reading")

        if not station_wallets_list:
            messages.error(
                request,
                "Aucun wallet n'est configuré pour cette station.",
            )
            return redirect("pumps:bulk_pump_reading")

        employee = Employee.objects.filter(user=request.user, station=station).first()
        seen_uuids = set()
        prepared = []

        for idx, item in enumerate(readings_data):
            pu = str(item.get("pump_uuid", "")).strip()
            ci_raw = str(item.get("current_index", "")).strip()
            if not pu or not ci_raw:
                messages.error(
                    request,
                    f"Lecture {idx + 1} : pompe et index actuel obligatoires.",
                )
                return redirect("pumps:bulk_pump_reading")
            if pu in seen_uuids:
                messages.error(
                    request,
                    "Vous ne pouvez pas saisir deux fois la même pompe dans une même saisie.",
                )
                return redirect("pumps:bulk_pump_reading")
            seen_uuids.add(pu)

            pump = Pump.objects.filter(pump_uuid=pu, station=station).first()
            if not pump:
                messages.error(request, "Pompe invalide ou non autorisée.")
                return redirect("pumps:bulk_pump_reading")

            try:
                current_index_decimal = Decimal(ci_raw)
            except (InvalidOperation, ValueError):
                messages.error(
                    request,
                    f'Index actuel invalide pour "{pump.name}".',
                )
                return redirect("pumps:bulk_pump_reading")

            latest = (
                PumpReading.objects.filter(pump=pump)
                .order_by("-reading_date", "-created_at")
                .first()
            )
            initial_index_decimal = latest.current_index if latest else Decimal("0")

            if current_index_decimal <= initial_index_decimal:
                messages.error(
                    request,
                    f'L\'index actuel doit être supérieur à l\'index précédent pour "{pump.name}".',
                )
                return redirect("pumps:bulk_pump_reading")

            readings_count = PumpReading.objects.filter(pump=pump).count()
            existing_today = PumpReading.objects.filter(
                pump=pump, reading_date=today
            ).first()
            if readings_count > 1 and existing_today:
                messages.error(
                    request,
                    f'Une lecture a déjà été enregistrée aujourd\'hui pour "{pump.name}".',
                )
                return redirect("pumps:bulk_pump_reading")

            prepared.append(
                {
                    "pump": pump,
                    "previous_current": initial_index_decimal,
                    "current_index": current_index_decimal,
                }
            )

        total_batch = Decimal("0")
        for row in prepared:
            total_batch += _compute_sale_total_for_pump_reading(
                row["pump"], row["previous_current"], row["current_index"]
            )

        if total_batch > 0:
            allocations_by_uuid, err_resp = _parse_and_validate_wallet_allocations(
                request, allocations_json, station_wallets_list, total_batch
            )
            if err_resp is not None:
                return err_resp
        else:
            allocations_by_uuid = {}

        try:
            with transaction.atomic():
                for row in prepared:
                    reading = PumpReading.objects.create(
                        pump=row["pump"],
                        employee=employee,
                        current_index=row["current_index"],
                        reading_date=today,
                    )
                    sale = _create_sale_from_reading(reading, request.user)
                    _trace_daily_stock_from_sale(sale, request.user)
                    _record_inventory_out_and_decrease_station_stock(sale)

                for wallet_uuid, amount in allocations_by_uuid.items():
                    if amount <= 0:
                        continue
                    w = Account.objects.select_for_update().get(
                        uuid=wallet_uuid, station=station
                    )
                    w.balance = (w.balance or Decimal("0")) + amount
                    w.save(update_fields=["balance", "updated_at"])
        except IntegrityError as exc:
            messages.error(request, f"Erreur lors de l'enregistrement : {exc}")
            return redirect("pumps:bulk_pump_reading")

        messages.success(
            request,
            f"{len(prepared)} lecture(s) enregistrée(s) et montants répartis sur les wallets.",
        )
        return redirect("pumps:pumps_list")

    context = {
        "station": station,
        "bulk_reading_station_uuid": bulk_station_uuid_for_form,
        "pumps_data": pumps_data,
        "station_wallets": [
            {
                "uuid": str(w.uuid),
                "name": w.name,
                "currency": w.currency,
            }
            for w in station_wallets_list
        ],
        "product_price_essence": str(
            Decimal(str(getattr(settings, "PRODUCT_PRICE_ESSENCE", 0)))
        ),
        "product_price_diesel": str(
            Decimal(str(getattr(settings, "PRODUCT_PRICE_DIESEL", 0)))
        ),
    }
    return render(request, "pumps/bulk_pump_reading.html", context)


@login_required
def reset_pump_view(request, pump_uuid):
    """
    Réinitialise une pompe (index initial et actuel à 0).
    Action autorisée uniquement pour l'admin propriétaire.
    """
    if request.method != "POST":
        return redirect("pumps:pump_detail", pump_uuid=pump_uuid)

    try:
        pump = get_object_or_404(Pump, pump_uuid=pump_uuid)

        if request.user.role != "admin":
            messages.error(request, "Seul un administrateur peut réinitialiser une pompe.")
            return redirect("pumps:pump_detail", pump_uuid=pump_uuid)

        if pump.station.owner != request.user:
            messages.error(request, "Vous n'avez pas la permission de réinitialiser cette pompe.")
            return redirect("pumps:pumps_list")

        ordered = list(
            PumpReading.objects.filter(pump=pump).order_by("-reading_date", "-created_at", "-id")
        )
        latest_reading = ordered[0] if ordered else None
        second_reading = ordered[1] if len(ordered) > 1 else None
        previous_initial = second_reading.current_index if second_reading else Decimal("0")
        previous_current = latest_reading.current_index if latest_reading else Decimal("0")
        reason = request.POST.get("reason", "").strip()

        PumpReset.objects.create(
            pump=pump,
            previous_initial_index=previous_initial,
            previous_current_index=previous_current,
            reset_initial_index=Decimal("0"),
            reset_current_index=Decimal("0"),
            reason=reason or None,
            reset_by=request.user,
        )

        PumpReading.objects.create(
            pump=pump,
            employee=None,
            current_index=Decimal("0"),
            reading_date=timezone.now().date(),
        )

        messages.success(request, f'La pompe "{pump.name}" a été réinitialisée à 0.')
    except Exception as e:
        messages.error(request, f"Erreur lors de la réinitialisation : {str(e)}")

    return redirect("pumps:pump_detail", pump_uuid=pump_uuid)
