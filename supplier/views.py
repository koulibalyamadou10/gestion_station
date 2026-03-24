from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from supplier.models import Supplier


@login_required
def supplier_list_view(request):
    """
    Liste des fournisseurs + création (modal).
    Réservé aux administrateurs (propriétaires).
    Modification / suppression : vues dédiées + modales sur cette page.
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


@login_required
def supplier_update_view(request, supplier_id):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method != "POST":
        return redirect("supplier:supplier_list")

    name = request.POST.get("name", "").strip()
    contact = request.POST.get("contact", "").strip() or None
    address = request.POST.get("address", "").strip() or None
    phone = request.POST.get("phone", "").strip() or None

    if not name:
        messages.error(request, "Le nom du fournisseur est obligatoire.")
        return redirect("supplier:supplier_list")

    if Supplier.objects.filter(name__iexact=name).exclude(pk=supplier.pk).exists():
        messages.error(request, "Un autre fournisseur porte déjà ce nom.")
        return redirect("supplier:supplier_list")

    supplier.name = name
    supplier.contact = contact
    supplier.address = address
    supplier.phone = phone
    supplier.save()
    messages.success(request, "Fournisseur modifié avec succès.")
    return redirect("supplier:supplier_list")


@login_required
def supplier_delete_view(request, supplier_id):
    if request.user.role != "admin":
        messages.error(request, "Vous n'avez pas la permission d'accéder à cette page.")
        return redirect("account:not_access")

    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method != "POST":
        return redirect("supplier:supplier_list")

    if supplier.order_suppliers.exists():
        messages.error(
            request,
            "Impossible de supprimer ce fournisseur : il est lié à une ou plusieurs commandes.",
        )
        return redirect("supplier:supplier_list")

    nom = supplier.name
    supplier.delete()
    messages.success(request, f'Fournisseur « {nom} » supprimé.')
    return redirect("supplier:supplier_list")
