from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from account.models import CustomUser
from permissions_web import super_admin_required, admin_required

@csrf_protect
def login_view(request):
    """
    Vue pour gérer la connexion des utilisateurs
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            messages.error(request, 'Veuillez remplir tous les champs.')
            return render(request, 'account/login.html')
        
        # Authentification avec email (USERNAME_FIELD)
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Bienvenue {user.get_full_name()} !')
                # Redirection vers le dashboard
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Votre compte est désactivé.')
        else:
            messages.error(request, 'Email ou mot de passe incorrect.')
    
    return render(request, 'account/login.html')

@login_required
def dashboard_view(request):
    """
    Vue pour le tableau de bord après connexion
    """
    return render(request, 'dashboard/dashboard.html', {
        'user': request.user
    })

def logout_view(request):
    """
    Vue pour déconnecter l'utilisateur
    """
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('home')

@super_admin_required
def users_list_view(request):
    """
    Vue pour afficher la liste des utilisateurs
    Accessible uniquement aux super_admins
    """
    # Récupérer tous les utilisateurs
    users = CustomUser.objects.all().order_by('-created_at')
    
    # Filtres et recherche
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    
    # Appliquer les filtres
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)
    
    # Statistiques
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    super_admins = CustomUser.objects.filter(role='super_admin').count()
    admins = CustomUser.objects.filter(role='admin').count()
    managers = CustomUser.objects.filter(role='manager').count()
    
    context = {
        'users': users,
        'total_users': total_users,
        'active_users': active_users,
        'super_admins': super_admins,
        'admins': admins,
        'managers': managers,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': CustomUser.ROLE_CHOICES,
    }
    
    return render(request, 'account/user_content.html', context)

@login_required
def not_access_view(request):
    """
    Vue pour afficher le message d'accès refusé
    """
    return render(request, 'account/not_access.html')
