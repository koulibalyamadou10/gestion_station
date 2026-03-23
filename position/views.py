from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from position.models import Position


@login_required
def position_list_view(request):
    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page")

    positions_queryset = Position.objects.order_by("-created_at")
    if search_query:
        positions_queryset = positions_queryset.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    paginator = Paginator(positions_queryset, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        "positions": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_positions": positions_queryset.count(),
    }
    return render(request, "position_content.html", context)


@login_required
def create_position_view(request):
    if request.method != "POST":
        return redirect("position:position_list")

    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()

    if not title:
        messages.error(request, "Le nom du poste est obligatoire.")
        return redirect("position:position_list")

    Position.objects.create(
        title=title,
        description=description or None,
    )
    messages.success(request, "Poste créé avec succès.")
    return redirect("position:position_list")


@login_required
def update_position_view(request, uuid):
    if request.method != "POST":
        return redirect("position:position_list")

    position = get_object_or_404(Position, uuid=uuid)
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()

    if not title:
        messages.error(request, "Le nom du poste est obligatoire.")
        return redirect("position:position_list")

    position.title = title
    position.description = description or None
    position.save(update_fields=["title", "description", "updated_at"])
    messages.success(request, "Poste modifié avec succès.")
    return redirect("position:position_list")


@login_required
def delete_position_view(request, uuid):
    if request.method != "POST":
        return redirect("position:position_list")

    position = get_object_or_404(Position, uuid=uuid)
    position.delete()
    messages.success(request, "Poste supprimé avec succès.")
    return redirect("position:position_list")
