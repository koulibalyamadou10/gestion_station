from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

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

    if not station_id or not name or not product:
        messages.error(request, "Veuillez remplir tous les champs obligatoires.")
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

    Tank.objects.create(
        station=station,
        name=name,
        product=product,
        description=description or None,
        actual_quantity=actual_quantity,
        max_capacity=max_capacity,
    )

    # Synchroniser le stock station à partir de la somme des cuves du même produit
    if product == Tank.PRODUCT_GASOLINE:
        station.stock_gasoline = (
            Tank.objects.filter(station=station, product=Tank.PRODUCT_GASOLINE).aggregate(
                total=Sum("actual_quantity")
            )["total"]
            or Decimal("0.00")
        )
        station.save(update_fields=["stock_gasoline", "updated_at"])
    elif product == Tank.PRODUCT_DIESEL:
        station.stock_diesel = (
            Tank.objects.filter(station=station, product=Tank.PRODUCT_DIESEL).aggregate(
                total=Sum("actual_quantity")
            )["total"]
            or Decimal("0.00")
        )
        station.save(update_fields=["stock_diesel", "updated_at"])

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
