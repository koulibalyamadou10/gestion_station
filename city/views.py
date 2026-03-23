from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from city.models import City


@login_required
def city_list_view(request):
    if request.user.role not in ["admin", "super_admin"]:
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:dashboard")

    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page")

    cities_queryset = City.objects.order_by("-created_at")
    if search_query:
        cities_queryset = cities_queryset.filter(Q(name__icontains=search_query))

    paginator = Paginator(cities_queryset, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        "cities": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_cities": cities_queryset.count(),
    }
    return render(request, "city_content.html", context)


@login_required
def create_city_view(request):
    if request.user.role not in ["admin", "super_admin"]:
        messages.error(request, "Vous n'avez pas la permission de créer une ville.")
        return redirect("account:dashboard")

    if request.method != "POST":
        return redirect("city:city_list")

    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Le nom de la ville est obligatoire.")
        return redirect("city:city_list")

    if City.objects.filter(name__iexact=name).exists():
        messages.error(request, "Cette ville existe déjà.")
        return redirect("city:city_list")

    City.objects.create(name=name)
    messages.success(request, "Ville créée avec succès.")
    return redirect("city:city_list")


@login_required
def update_city_view(request, city_id):
    if request.user.role not in ["admin", "super_admin"]:
        messages.error(request, "Vous n'avez pas la permission de modifier une ville.")
        return redirect("account:dashboard")

    if request.method != "POST":
        return redirect("city:city_list")

    city = get_object_or_404(City, id=city_id)
    name = request.POST.get("name", "").strip()

    if not name:
        messages.error(request, "Le nom de la ville est obligatoire.")
        return redirect("city:city_list")

    if City.objects.filter(name__iexact=name).exclude(id=city.id).exists():
        messages.error(request, "Une autre ville porte déjà ce nom.")
        return redirect("city:city_list")

    city.name = name
    city.save(update_fields=["name", "updated_at"])
    messages.success(request, "Ville modifiée avec succès.")
    return redirect("city:city_list")


@login_required
def delete_city_view(request, city_id):
    if request.user.role not in ["admin", "super_admin"]:
        messages.error(request, "Vous n'avez pas la permission de supprimer une ville.")
        return redirect("account:dashboard")

    if request.method != "POST":
        return redirect("city:city_list")

    city = get_object_or_404(City, id=city_id)
    city_name = city.name
    city.delete()
    messages.success(request, f'Ville "{city_name}" supprimée avec succès.')
    return redirect("city:city_list")
