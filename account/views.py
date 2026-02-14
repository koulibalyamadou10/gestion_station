from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from account.models import CustomUser
from permissions_web import super_admin_required, admin_required
import secrets
import string

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

@super_admin_required
def delete_user_view(request, user_id):
    """
    Vue pour supprimer définitivement un utilisateur
    Accessible uniquement aux super_admins
    """
    if request.method == 'POST':
        try:
            user_to_delete = CustomUser.objects.get(id=user_id)
            
            # Empêcher la suppression de soi-même
            if user_to_delete.id == request.user.id:
                messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte.')
                return redirect('users_list')
            
            # Empêcher la suppression d'un autre super_admin
            if user_to_delete.role == 'super_admin':
                messages.error(request, 'Vous ne pouvez pas supprimer un autre Super Administrateur.')
                return redirect('users_list')
            
            user_name = user_to_delete.get_full_name()
            user_to_delete.delete()
            
            messages.success(request, f'Utilisateur {user_name} supprimé définitivement avec succès.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Utilisateur introuvable.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    
    return redirect('users_list')

def generate_password(length=12):
    """
    Génère un mot de passe sécurisé aléatoire
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

@super_admin_required
def create_user_view(request):
    """
    Vue pour créer un nouvel utilisateur (admin uniquement)
    Accessible uniquement aux super_admins
    Génère automatiquement un mot de passe et l'envoie par email
    """
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_code = request.POST.get('phone_code')
        phone_number = request.POST.get('phone_number')
        role = request.POST.get('role', 'admin')  # Par défaut admin
        
        # Validation
        errors = []
        
        if not first_name or not last_name:
            errors.append('Le prénom et le nom sont requis.')
        
        if not email:
            errors.append('L\'email est requis.')
        elif CustomUser.objects.filter(email=email).exists():
            errors.append('Cet email est déjà utilisé.')
        
        if not phone_code or not phone_number:
            errors.append('Le code et le numéro de téléphone sont requis.')
        
        # Le super_admin ne peut créer que des admins
        if role != 'admin':
            errors.append('Vous ne pouvez créer que des utilisateurs avec le rôle Admin.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Générer un mot de passe sécurisé
                generated_password = generate_password(16)
                
                # Créer l'utilisateur
                user = CustomUser.objects.create_user(
                    email=email,
                    password=generated_password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_code=phone_code,
                    phone_number=phone_number,
                    role='admin',  # Forcé à admin
                    is_active=True
                )
                
                # Envoyer l'email avec le mot de passe via la méthode du modèle
                login_url = request.build_absolute_uri('/login/')
                email_sent = user.send_credentials_email(generated_password, login_url)
                
                if email_sent:
                    messages.success(
                        request, 
                        f'Utilisateur {user.get_full_name()} créé avec succès ! Un email avec les identifiants a été envoyé à {user.email}.'
                    )
                else:
                    # Si l'envoi d'email échoue, on crée quand même l'utilisateur mais on affiche un avertissement
                    messages.warning(
                        request, 
                        f'Utilisateur {user.get_full_name()} créé avec succès, mais l\'envoi de l\'email a échoué. '
                        f'Mot de passe généré : {generated_password} (Veuillez le noter et le communiquer manuellement).'
                    )
                
                return redirect('users_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de la création : {str(e)}')
    
    return redirect('users_list')
