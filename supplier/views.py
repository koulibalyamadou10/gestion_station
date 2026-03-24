from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from supplier.models import Supplier


@login_required
def supplier_list_view(request):
    """
    Liste des fournisseurs + création (modal).
    Réservé aux administrateurs (propriétaires).
    Pas de modification ni suppression pour le moment.
    """
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        contact = request.POST.get("contact", "").strip() or None
        address = request.POST.get("address", "").strip() or None
        phone = request.POST.get("phone", "").strip() or None

        if not name:
            messages.error(request, "Le nom du fournisseur est obligatoire.")
            return redirect("supplier:supplier_list")

        if Supplier.objects.filter(name__iexact=name).exists():
            messages.error(request, "Un fournisseur avec ce nom existe déjà.")
            return redirect("supplier:supplier_list")

        Supplier.objects.create(
            name=name,
            contact=contact,
            address=address,
            phone=phone,
        )
        messages.success(request, "Fournisseur créé avec succès.")
        return redirect("supplier:supplier_list")

    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page")

    suppliers_qs = Supplier.objects.all().order_by("-created_at")
    if search_query:
        suppliers_qs = suppliers_qs.filter(
            Q(name__icontains=search_query)
            | Q(contact__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    paginator = Paginator(suppliers_qs, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        "suppliers": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_suppliers": suppliers_qs.count(),
    }
    return render(request, "supplier_content.html", context)
