from account.models import CustomUser
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from employee.models import Employee
from position.models import Position
from stations.models import Station


@login_required
def employee_list_view(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        hire_date = request.POST.get("hire_date", "").strip()
        station_id = request.POST.get("station", "").strip()
        position_id = request.POST.get("position", "").strip()
        user_id = request.POST.get("user", "").strip()

        if not first_name or not last_name or not station_id:
            messages.error(request, "Prénom, nom et station sont obligatoires.")
            return redirect("employee:employee_list")

        try:
            station = Station.objects.get(id=station_id)
        except Station.DoesNotExist:
            messages.error(request, "La station sélectionnée est invalide.")
            return redirect("employee:employee_list")

        position = None
        if position_id:
            try:
                position = Position.objects.get(id=position_id)
            except Position.DoesNotExist:
                messages.error(request, "Le poste sélectionné est invalide.")
                return redirect("employee:employee_list")

        user = None
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id, is_active=True)
            except CustomUser.DoesNotExist:
                messages.error(request, "L'utilisateur sélectionné est invalide.")
                return redirect("employee:employee_list")

            # Empêcher qu'un même gérant soit rattaché à plusieurs stations.
            existing_employee = Employee.objects.filter(user=user).exclude(station=station).first()
            if existing_employee:
                messages.error(
                    request,
                    (
                        f"Ce gérant est déjà rattaché à la station "
                        f"\"{existing_employee.station.name}\"."
                    ),
                )
                return redirect("employee:employee_list")

        Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone=phone or None,
            hire_date=hire_date or None,
            station=station,
            position=position,
            user=user,
        )
        messages.success(request, "Employé créé avec succès.")
        return redirect("employee:employee_list")

    search_query = request.GET.get("search", "").strip()
    page_number = request.GET.get("page")

    employees_queryset = Employee.objects.select_related(
        "position", "station", "user"
    ).order_by("-created_at")

    if search_query:
        employees_queryset = employees_queryset.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(position__title__icontains=search_query)
            | Q(station__name__icontains=search_query)
        )

    paginator = Paginator(employees_queryset, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        "employees": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_employees": employees_queryset.count(),
        "stations": Station.objects.order_by("name"),
        "positions": Position.objects.order_by("title"),
        "users": CustomUser.objects.filter(role="manager", is_active=True).order_by("first_name", "last_name"),
    }
    return render(request, "employee/employee_content.html", context)
