from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme

from daily_stock.models import DailyStock, DailyStockTankLine
from inventory.models import Inventory
from stations.models import Station
from tank.models import Tank


def _redirect_after_tank_form(request):
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("stations:stations_list")


def _user_can_manage_station_tanks(user, station):
    if user.role == "super_admin":
        return True
    if user.role == "admin" and station.owner_id == user.id:
        return True
    return False


def _sync_station_stock_from_tanks(station):
    """Recalcule stock essence / gazoil station = somme des cuves par produit."""
    station.stock_gasoline = (
        Tank.objects.filter(station=station, product=Tank.PRODUCT_GASOLINE).aggregate(
            total=Sum("actual_quantity")
        )["total"]
        or Decimal("0.00")
    )
    station.stock_diesel = (
        Tank.objects.filter(station=station, product=Tank.PRODUCT_DIESEL).aggregate(
            total=Sum("actual_quantity")
        )["total"]
        or Decimal("0.00")
    )
    station.save(update_fields=["stock_gasoline", "stock_diesel", "updated_at"])


def _previous_inventory_qty_before_date(station, reading_date):
    prev_row = (
        Inventory.objects.filter(station=station)
        .filter(
            Q(reading_date__lt=reading_date)
            | Q(reading_date__isnull=True, created_at__date__lt=reading_date)
        )
        .order_by("-reading_date", "-created_at", "-id")
        .first()
    )
    if prev_row:
        return prev_row.qty_gasoline or Decimal("0.00"), prev_row.qty_diesel or Decimal("0.00")
    return Decimal("0.00"), Decimal("0.00")


def _upsert_tank_init_inventory(station, reading_date, product):
    """
    Une ligne stock_reel par station + date (création cuve).
    Si une ligne existe déjà ce jour : on conserve l'autre produit et on met à jour
    essence ou gazoil selon la cuve créée.
    """
    existing = Inventory.objects.filter(
        station=station,
        reading_date=reading_date,
        source=Inventory.SOURCE_TANK_INIT,
    ).first()

    if existing:
        update_fields = ["updated_at"]
        if product == Tank.PRODUCT_GASOLINE:
            existing.qty_gasoline = station.stock_gasoline
            update_fields.append("qty_gasoline")
        else:
            existing.qty_diesel = station.stock_diesel
            update_fields.append("qty_diesel")
        existing.save(update_fields=update_fields)
        return existing

    prev_g, prev_d = _previous_inventory_qty_before_date(station, reading_date)
    return Inventory.objects.create(
        station=station,
        qty_gasoline=station.stock_gasoline,
        qty_diesel=station.stock_diesel,
        source=Inventory.SOURCE_TANK_INIT,
        reading_date=reading_date,
        previous_stock_gasoline=prev_g,
        previous_stock_diesel=prev_d,
        created_at=timezone.make_aware(
            timezone.datetime.combine(reading_date, timezone.datetime.min.time()),
            timezone.get_current_timezone(),
        ),
    )


def _upsert_tank_init_daily_stock(station, stock_date, product, tank, recorded_by, prev_station_g, prev_station_d):
    """
    Stock journalier (gérant) : une ligne par station + date.
    Même jour : conserver l'autre produit, mettre à jour essence ou gazoil (somme des cuves).
    """
    existing = DailyStock.objects.filter(station=station, stock_date=stock_date).first()

    if existing:
        update_fields = ["updated_at"]
        if product == Tank.PRODUCT_GASOLINE:
            existing.qty_gasoline = station.stock_gasoline
            update_fields.append("qty_gasoline")
        else:
            existing.qty_diesel = station.stock_diesel
            update_fields.append("qty_diesel")
        existing.save(update_fields=update_fields)
        daily_stock = existing
    else:
        daily_stock = DailyStock.objects.create(
            station=station,
            stock_date=stock_date,
            recorded_by=recorded_by,
            qty_gasoline=station.stock_gasoline,
            qty_diesel=station.stock_diesel,
            previous_stock_gasoline=prev_station_g,
            previous_stock_diesel=prev_station_d,
        )

    DailyStockTankLine.objects.update_or_create(
        daily_stock=daily_stock,
        tank=tank,
        defaults={
            "previous_quantity": Decimal("0.00"),
            "recorded_quantity": tank.actual_quantity or Decimal("0.00"),
        },
    )
    return daily_stock


@login_required
def create_tank_view(request):
    """Création d'une cuve pour une station (admin propriétaire ou super_admin)."""
    if request.user.role not in ("admin", "super_admin"):
        messages.error(request, "Seul l'administrateur peut créer une cuve.")
        return redirect("stations:stations_list")

    if request.method != "POST":
        return redirect("stations:stations_list")

    station_id = (request.POST.get("station_id") or "").strip()
    name = (request.POST.get("name") or "").strip()
    product = (request.POST.get("product") or "").strip()
    description = (request.POST.get("description") or "").strip()
    actual_quantity_raw = (request.POST.get("actual_quantity") or "0").strip()
    max_capacity_raw = (request.POST.get("max_capacity") or "").strip()
    reading_date_raw = (request.POST.get("reading_date") or "").strip()

    if not station_id or not name or not product:
        messages.error(request, "Veuillez remplir tous les champs obligatoires.")
        return _redirect_after_tank_form(request)

    reading_date = parse_date(reading_date_raw)
    if not reading_date:
        messages.error(request, "Veuillez indiquer une date de relevé valide.")
        return _redirect_after_tank_form(request)

    if product not in (Tank.PRODUCT_GASOLINE, Tank.PRODUCT_DIESEL):
        messages.error(request, "Type de produit invalide. Choisissez Essence ou Gazoil.")
        return _redirect_after_tank_form(request)

    try:
        actual_quantity = Decimal(
            actual_quantity_raw.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
        ).quantize(Decimal("0.01"))
        if actual_quantity < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        messages.error(request, "La quantité actuelle doit être un nombre positif ou nul.")
        return _redirect_after_tank_form(request)

    max_capacity = None
    if max_capacity_raw:
        try:
            max_capacity = Decimal(
                max_capacity_raw.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
            ).quantize(Decimal("0.01"))
            if max_capacity < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, "La quantité maximale doit être un nombre positif ou nul.")
            return _redirect_after_tank_form(request)

    if request.user.role == "admin":
        station = Station.objects.filter(id=station_id, owner=request.user).first()
    else:
        station = Station.objects.filter(id=station_id).first()

    if not station:
        messages.error(request, "Station invalide pour cet utilisateur.")
        return _redirect_after_tank_form(request)

    if not _user_can_manage_station_tanks(request.user, station):
        messages.error(request, "Vous n'avez pas la permission de gérer les cuves de cette station.")
        return _redirect_after_tank_form(request)

    if Tank.objects.filter(station=station, name__iexact=name).exists():
        messages.error(request, f'La cuve "{name}" existe déjà pour cette station.')
        return _redirect_after_tank_form(request)

    with transaction.atomic():
        station_locked = Station.objects.select_for_update().get(pk=station.pk)
        prev_station_g = station_locked.stock_gasoline or Decimal("0.00")
        prev_station_d = station_locked.stock_diesel or Decimal("0.00")

        tank = Tank.objects.create(
            station=station_locked,
            name=name,
            product=product,
            description=description or None,
            actual_quantity=actual_quantity,
            max_capacity=max_capacity,
        )
        _sync_station_stock_from_tanks(station_locked)
        station_locked.refresh_from_db()

        _upsert_tank_init_inventory(station_locked, reading_date, product)
        _upsert_tank_init_daily_stock(
            station_locked,
            reading_date,
            product,
            tank,
            request.user,
            prev_station_g,
            prev_station_d,
        )

    messages.success(request, f'Cuve "{name}" créée avec succès.')
    return _redirect_after_tank_form(request)


@login_required
def update_tank_max_capacity_view(request, tank_uuid):
    """Modification de la quantité maximale d'une cuve (admin propriétaire ou super_admin)."""
    if request.user.role not in ("admin", "super_admin"):
        messages.error(request, "Seul l'administrateur peut modifier une cuve.")
        return redirect("stations:stations_list")

    if request.method != "POST":
        return redirect("stations:stations_list")

    tank = Tank.objects.select_related("station").filter(tank_uuid=tank_uuid).first()
    if not tank:
        messages.error(request, "Cuve introuvable.")
        return _redirect_after_tank_form(request)

    station = tank.station
    if not _user_can_manage_station_tanks(request.user, station):
        messages.error(request, "Vous n'avez pas la permission de gérer les cuves de cette station.")
        return _redirect_after_tank_form(request)

    max_capacity_raw = (request.POST.get("max_capacity") or "").strip()
    max_capacity = None
    if max_capacity_raw:
        try:
            max_capacity = Decimal(
                max_capacity_raw.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
            ).quantize(Decimal("0.01"))
            if max_capacity < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, "La quantité maximale doit être un nombre positif ou nul.")
            return _redirect_after_tank_form(request)

    tank.max_capacity = max_capacity
    tank.save(update_fields=["max_capacity", "updated_at"])
    messages.success(request, f'La quantité maximale de la cuve "{tank.name}" a été mise à jour.')
    return _redirect_after_tank_form(request)


def _verify_deletion_password(request):
    password = (request.POST.get("password") or "").strip()
    if not password:
        messages.error(
            request,
            "Veuillez saisir votre mot de passe pour confirmer la suppression.",
        )
        return False
    if not request.user.check_password(password):
        messages.error(request, "Mot de passe incorrect.")
        return False
    return True


@login_required
def delete_tank_view(request, tank_uuid):
    """Suppression d'une cuve (admin propriétaire ou super_admin)."""
    if request.user.role not in ("admin", "super_admin"):
        messages.error(request, "Seul l'administrateur peut supprimer une cuve.")
        return redirect("stations:stations_list")

    if request.method != "POST":
        return redirect("stations:stations_list")

    if not _verify_deletion_password(request):
        return _redirect_after_tank_form(request)

    tank = Tank.objects.select_related("station").filter(tank_uuid=tank_uuid).first()
    if not tank:
        messages.error(request, "Cuve introuvable.")
        return _redirect_after_tank_form(request)

    station = tank.station
    if not _user_can_manage_station_tanks(request.user, station):
        messages.error(request, "Vous n'avez pas la permission de gérer les cuves de cette station.")
        return _redirect_after_tank_form(request)

    from pumps.models import Pump

    pumps_count = Pump.objects.filter(tank=tank).count()
    if pumps_count > 0:
        messages.error(
            request,
            f'Suppression impossible : la cuve "{tank.name}" est liée à {pumps_count} pompe(s). '
            "Supprimez d'abord les pompes associées.",
        )
        return _redirect_after_tank_form(request)

    tank_name = tank.name
    with transaction.atomic():
        station_locked = Station.objects.select_for_update().get(pk=station.pk)
        tank.delete()
        _sync_station_stock_from_tanks(station_locked)

    messages.success(request, f'Cuve "{tank_name}" supprimée avec succès.')
    return _redirect_after_tank_form(request)
