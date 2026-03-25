from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils.text import slugify
from account.models import CustomUser
from permissions_web import super_admin_required, admin_required
import re
import secrets
import string
from employee.models import Employee

_USERNAME_PATTERN = re.compile(r"^[\w.-]+$", re.UNICODE)


def _allocate_unique_username(base: str) -> str:
    base = (base or "").strip()[:80] or "gerant"
    candidate = base
    n = 0
    while CustomUser.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def _resolve_manager_username(post, first_name, last_name, email, errors):
    """
    Nom d'utilisateur saisi (unique) ou généré à partir de l'email / nom.
    """
    raw = (post.get("username") or "").strip()
    if raw:
        if len(raw) < 3 or len(raw) > 150:
            errors.append("Le nom d'utilisateur doit contenir entre 3 et 150 caractères.")
            return None
        if not _USERNAME_PATTERN.match(raw):
            errors.append(
                "Le nom d'utilisateur ne peut contenir que des lettres, chiffres, points, tirets et underscores."
            )
            return None
        if CustomUser.objects.filter(username__iexact=raw).exists():
            errors.append("Ce nom d'utilisateur est déjà utilisé.")
            return None
        return raw
    local = (email or "").split("@")[0].strip()
    base = slugify(local) or slugify(f"{first_name}-{last_name}") or "gerant"
    return _allocate_unique_username(base)

@csrf_protect
def login_view(request):
    """
    Vue pour gérer la connexion des utilisateurs
    """
    if request.user.is_authenticated:
        return redirect('account:dashboard')
    
    if request.method == 'POST':
        password = request.POST.get('password')
        login_mode = (request.POST.get('login_mode') or 'email').strip()
        print(login_mode)
        print(request.POST.get('username'))
        print(request.POST.get('email'))
        print(request.POST.get('password'))
        print(request.POST.get('login_mode'))
        if login_mode == 'username':
            raw_username = (request.POST.get('username') or '').strip()
            if not raw_username or not password:
                messages.error(request, 'Veuillez remplir tous les champs.')
                return render(request, 'account/login.html')
            user_row = CustomUser.objects.filter(username__iexact=raw_username).only('email').first()
            if user_row is None:
                messages.error(request, 'Nom d’utilisateur ou mot de passe incorrect.')
                return render(request, 'account/login.html')
            user = authenticate(request, username=user_row.email, password=password)
        else:
            email = (request.POST.get('email') or '').strip()
            if not email or not password:
                messages.error(request, 'Veuillez remplir tous les champs.')
                return render(request, 'account/login.html')
            user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Bienvenue {user.get_full_name()} !')
                next_url = request.GET.get('next', 'account:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Votre compte est désactivé.')
        else:
            messages.error(request, 'Identifiant ou mot de passe incorrect.')
    
    return render(request, 'account/login.html')

@login_required
def dashboard_view(request):
    """
    Vue pour le tableau de bord après connexion
    """
    return render(request, 'dashboard/dashboard.html', {
        'user': request.user
    })

@csrf_protect
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
def delete_user_view(request, user_uuid):
    """
    Vue pour supprimer définitivement un utilisateur
    Accessible uniquement aux super_admins
    """
    if request.method == 'POST':
        try:
            user_to_delete = CustomUser.objects.get(user_uuid=user_uuid)
            
            # Empêcher la suppression de soi-même
            if user_to_delete.user_uuid == request.user.user_uuid:
                messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte.')
                return redirect('account:users_list')
            
            # Empêcher la suppression d'un autre super_admin
            if user_to_delete.role == 'super_admin':
                messages.error(request, 'Vous ne pouvez pas supprimer un autre Super Administrateur.')
                return redirect('account:users_list')
            
            user_name = user_to_delete.get_full_name()
            user_to_delete.delete()
            
            messages.success(request, f'Utilisateur {user_name} supprimé définitivement avec succès.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Utilisateur introuvable.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    
    return redirect('account:users_list')

def generate_password(length=12):
    """
    Génère un mot de passe aléatoire (minuscules + chiffres)
    """
    alphabet = string.ascii_lowercase + string.digits
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
                generated_password = generate_password(8)
                
                # Créer l'utilisateur
                user = CustomUser.objects.create_user(
                    email=email,
                    password=generated_password,
                    first_name=first_name,
                    last_name=last_name,
                    phone_code=phone_code,
                    phone_number=phone_number,
                    role='admin',  # Forcé à admin
                    is_active=True,
                    created_by=request.user  # Le super_admin qui crée l'admin
                )
                
                # Envoyer l'email avec le mot de passe via la méthode du modèle
                login_url = request.build_absolute_uri('/login/')
                email_sent = user.send_credentials_email(generated_password, login_url)

                print(generated_password)

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
                
                return redirect('account:users_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de la création : {str(e)}')
    
    return redirect('account:users_list')

@admin_required
def managers_list_view(request):
    """
    Vue pour afficher la liste des managers (gérants) d'un admin
    Accessible aux admins et super_admins
    """
    # Si super_admin, voir tous les managers
    # Si admin, voir uniquement ses managers
    if request.user.role == 'super_admin':
        managers = CustomUser.objects.filter(role='manager').order_by('-created_at')
    else:
        managers = CustomUser.objects.filter(role='manager', created_by=request.user).order_by('-created_at')
    
    # Filtres et recherche
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    # Appliquer les filtres
    if search_query:
        managers = managers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    if status_filter:
        if status_filter == 'active':
            managers = managers.filter(is_active=True)
        elif status_filter == 'inactive':
            managers = managers.filter(is_active=False)
    
    # Statistiques
    total_managers = managers.count()
    active_managers = managers.filter(is_active=True).count()
    inactive_managers = managers.filter(is_active=False).count()

    from stations.models import Station

    if request.user.role == 'super_admin':
        assignable_stations = Station.objects.select_related('city', 'owner').order_by('name')
    else:
        assignable_stations = (
            Station.objects.select_related('city', 'owner')
            .filter(owner=request.user)
            .order_by('name')
        )

    context = {
        'managers': managers,
        'total_managers': total_managers,
        'active_managers': active_managers,
        'inactive_managers': inactive_managers,
        'search_query': search_query,
        'status_filter': status_filter,
        'assignable_stations': assignable_stations,
    }
    
    return render(request, 'account/managers_content.html', context)

@admin_required
def create_manager_view(request):
    """
    Vue pour créer un nouveau manager (gérant)
    Accessible aux admins et super_admins
    """
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_code = request.POST.get('phone_code')
        phone_number = request.POST.get('phone_number')
        station_id = (request.POST.get('station_id') or '').strip()

        # Validation
        errors = []

        station = None
        if station_id:
            from stations.models import Station

            try:
                station = Station.objects.select_related('owner').get(pk=station_id)
            except (Station.DoesNotExist, ValueError):
                errors.append('La station sélectionnée est invalide.')
            if station is not None and request.user.role == 'admin':
                if station.owner_id != request.user.id:
                    errors.append('Vous ne pouvez pas assigner ce gérant à cette station.')
        
        if not first_name or not last_name:
            errors.append('Le prénom et le nom sont requis.')
        
        if not email:
            errors.append('L\'email est requis.')
        elif CustomUser.objects.filter(email=email).exists():
            errors.append('Cet email est déjà utilisé.')
        
        if not phone_code or not phone_number:
            errors.append('Le code et le numéro de téléphone sont requis.')

        resolved_username = _resolve_manager_username(
            request.POST, first_name, last_name, email, errors
        )
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Générer un mot de passe sécurisé
                generated_password = generate_password(8)

                print(generated_password)

                created_by_user = request.user
                if station and station.owner_id and request.user.role == 'super_admin':
                    created_by_user = station.owner
                
                # Créer le manager
                manager = CustomUser.objects.create_user(
                    email=email,
                    password=generated_password,
                    first_name=first_name,
                    last_name=last_name,
                    username=resolved_username,
                    phone_code=phone_code,
                    phone_number=phone_number,
                    role='manager',  # Forcé à manager
                    is_active=True,
                    created_by=created_by_user,
                )

                # creer l'employé aussi tout simplement quoi 
                Employee.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone_number,
                    user=manager,
                    station=station,
                    position=None,
                    hire_date=None,
                    # owner=request.user
                )

                if station:
                    from stations.models import StationManager

                    StationManager.objects.update_or_create(
                        station=station,
                        defaults={'manager': manager},
                    )
                
                # Envoyer l'email avec le mot de passe via la méthode du modèle
                login_url = request.build_absolute_uri('/login/')
                email_sent = manager.send_credentials_email(generated_password, login_url)
                
                if email_sent:
                    messages.success(
                        request, 
                        f'Gérant {manager.get_full_name()} créé avec succès ! Un email avec les identifiants a été envoyé à {manager.email}.'
                    )
                else:
                    messages.warning(
                        request, 
                        f'Gérant {manager.get_full_name()} créé avec succès, mais l\'envoi de l\'email a échoué. '
                        f'Mot de passe généré : {generated_password} (Veuillez le noter et le communiquer manuellement).'
                    )
                
                return redirect('account:managers_list')
            except Exception as e:
                messages.error(request, f'Erreur lors de la création : {str(e)}')
    
    return redirect('account:managers_list')

@admin_required
def update_manager_name_view(request, user_uuid):
    """
    Met à jour uniquement le prénom/nom d'un manager.
    Accessible aux admins et super_admins.
    """
    if request.method == 'POST':
        manager = get_object_or_404(CustomUser, user_uuid=user_uuid, role='manager')

        if request.user.role == 'admin' and manager.created_by != request.user:
            messages.error(request, "Vous n'avez pas la permission de modifier ce gérant.")
            return redirect('account:managers_list')

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if not first_name or not last_name:
            messages.error(request, 'Le prénom et le nom sont obligatoires.')
            return redirect('account:managers_list')

        manager.first_name = first_name
        manager.last_name = last_name
        manager.save(update_fields=['first_name', 'last_name', 'updated_at'])
        messages.success(request, 'Le gérant a été modifié avec succès.')

    return redirect('account:managers_list')

@login_required
def profile_view(request):
    """
    Vue pour afficher et modifier le profil de l'utilisateur connecté
    """
    user = request.user
    
    if request.method == 'POST':
        # Mise à jour des informations du profil
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_code = request.POST.get('phone_code')
        phone_number = request.POST.get('phone_number')
        
        if first_name and last_name:
            user.first_name = first_name
            user.last_name = last_name
        
        if phone_code and phone_number:
            import re
            user.phone_code = phone_code
            user.phone_number = re.sub(r'\D', '', phone_number)  # Enlever les séparateurs
        
        user.save()
        messages.success(request, 'Votre profil a été mis à jour avec succès.')
        return redirect('account:profile')
    
    context = {
        'user': user
    }
    
    return render(request, 'account/profile.html', context)

@login_required
def change_password_view(request):
    """
    Vue pour changer le mot de passe de l'utilisateur connecté
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Vérifier le mot de passe actuel
        if not request.user.check_password(current_password):
            messages.error(request, 'Le mot de passe actuel est incorrect.')
            return redirect('account:profile')
        
        # Vérifier que les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            messages.error(request, 'Les nouveaux mots de passe ne correspondent pas.')
            return redirect('account:profile')
        
        # Vérifier la longueur du nouveau mot de passe
        if len(new_password) < 8:
            messages.error(request, 'Le nouveau mot de passe doit contenir au moins 8 caractères.')
            return redirect('account:profile')
        
        # Changer le mot de passe
        request.user.set_password(new_password)
        request.user.save()
        
        # Ré-authentifier l'utilisateur pour éviter la déconnexion
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Votre mot de passe a été changé avec succès.')
        return redirect('account:profile')
    
    return redirect('account:profile')

@admin_required
def delete_manager_view(request, user_uuid):
    """
    Vue pour supprimer définitivement un manager
    Accessible aux admins et super_admins
    """
    if request.method == 'POST':
        try:
            manager_to_delete = get_object_or_404(CustomUser, user_uuid=user_uuid, role='manager')
            
            # Vérifier que l'admin peut supprimer ce manager
            if request.user.role == 'admin' and manager_to_delete.created_by != request.user:
                messages.error(request, 'Vous n\'avez pas la permission de supprimer ce gérant.')
                return redirect('account:managers_list')
            
            manager_name = manager_to_delete.get_full_name()
            manager_to_delete.delete()
            
            messages.success(request, f'Gérant {manager_name} supprimé définitivement avec succès.')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Gérant introuvable.')
        except Exception as e:
            messages.error(request, f'Erreur lors de la suppression : {str(e)}')
    
    return redirect('account:managers_list')

@admin_required
def toggle_manager_status_view(request, user_uuid):
    """
    Active ou désactive un manager.
    Accessible aux admins et super_admins.
    """
    if request.method == 'POST':
        manager = get_object_or_404(CustomUser, user_uuid=user_uuid, role='manager')

        if request.user.role == 'admin' and manager.created_by != request.user:
            messages.error(request, "Vous n'avez pas la permission de modifier ce gérant.")
            return redirect('account:managers_list')

        manager.is_active = not manager.is_active
        manager.save(update_fields=['is_active', 'updated_at'])

        if manager.is_active:
            messages.success(request, f'Le gérant {manager.get_full_name()} a été activé.')
        else:
            messages.success(request, f'Le gérant {manager.get_full_name()} a été désactivé.')

    return redirect('account:managers_list')

@admin_required
def reset_manager_password_view(request, user_uuid):
    """
    Réinitialise le mot de passe d'un manager et l'envoie par email.
    Accessible aux admins et super_admins.
    """
    if request.method == 'POST':
        manager = get_object_or_404(CustomUser, user_uuid=user_uuid, role='manager')

        if request.user.role == 'admin' and manager.created_by != request.user:
            messages.error(request, "Vous n'avez pas la permission de réinitialiser ce mot de passe.")
            return redirect('account:managers_list')

        try:
            generated_password = generate_password(8)
            print(generated_password)
            manager.set_password(generated_password)
            manager.save(update_fields=['password', 'updated_at'])

            login_url = request.build_absolute_uri('/login/')
            email_sent = manager.send_credentials_email(generated_password, login_url)

            if email_sent:
                messages.success(
                    request,
                    f"Mot de passe de {manager.get_full_name()} réinitialisé et envoyé par email."
                )
            else:
                messages.warning(
                    request,
                    f"Mot de passe réinitialisé mais email non envoyé. Nouveau mot de passe: {generated_password}"
                )
        except Exception as e:
            messages.error(request, f"Erreur lors de la réinitialisation: {str(e)}")

    return redirect('account:managers_list')

@login_required
def user_detail_view(request, user_uuid):
    """
    Vue pour afficher les détails d'un utilisateur
    Accessible selon les permissions :
    - super_admin : peut voir tous les utilisateurs
    - admin : peut voir ses managers et lui-même
    - manager : peut voir seulement lui-même
    """
    user_detail = get_object_or_404(CustomUser, user_uuid=user_uuid)
    
    # Vérifier les permissions
    if request.user.role == 'super_admin':
        # Super admin peut voir tous les utilisateurs
        pass
    elif request.user.role == 'admin':
        # Admin peut voir ses managers et lui-même
        if user_detail.role == 'manager' and user_detail.created_by != request.user:
            messages.error(request, 'Vous n\'avez pas la permission de voir cet utilisateur.')
            return redirect('account:managers_list')
        elif user_detail.role not in ['manager', 'admin'] and user_detail != request.user:
            messages.error(request, 'Vous n\'avez pas la permission de voir cet utilisateur.')
            return redirect('account:dashboard')
    elif request.user.role == 'manager':
        # Manager peut voir seulement lui-même
        if user_detail != request.user:
            messages.error(request, 'Vous n\'avez pas la permission de voir cet utilisateur.')
            return redirect('account:dashboard')
    else:
        # Autres rôles : seulement soi-même
        if user_detail != request.user:
            messages.error(request, 'Vous n\'avez pas la permission de voir cet utilisateur.')
            return redirect('account:dashboard')
    
    # Récupérer les stations associées
    stations = None
    managed_stations = None
    manager_assignment = None
    assignable_stations = None
    
    if user_detail.role == 'admin':
        # Stations créées par cet admin
        from stations.models import Station
        stations = Station.objects.filter(owner=user_detail).order_by('-created_at')
    elif user_detail.role == 'manager':
        # Stations gérées par ce manager
        from stations.models import StationManager
        station_managers = StationManager.objects.filter(manager=user_detail).select_related('station')
        managed_stations = [sm.station for sm in station_managers]
        manager_assignment = station_managers.first()

        from stations.models import Station
        if request.user.role == 'super_admin':
            assignable_stations = Station.objects.all().order_by('name')
        elif request.user.role == 'admin':
            assignable_stations = Station.objects.filter(owner=request.user).order_by('name')
    
    # Récupérer les managers créés (si admin)
    created_managers = None
    if user_detail.role == 'admin':
        created_managers = CustomUser.objects.filter(created_by=user_detail, role='manager').order_by('-created_at')
    
    context = {
        'user_detail': user_detail,
        'stations': stations,
        'managed_stations': managed_stations,
        'manager_assignment': manager_assignment,
        'assignable_stations': assignable_stations,
        'created_managers': created_managers,
    }
    
    return render(request, 'account/user_detail.html', context)

@login_required
def update_user_name_view(request, user_uuid):
    """
    Met à jour uniquement prénom/nom d'un utilisateur selon permissions.
    """
    if request.method != 'POST':
        return redirect('account:dashboard')

    user_to_update = get_object_or_404(CustomUser, user_uuid=user_uuid)

    if request.user.role == 'super_admin':
        pass
    elif request.user.role == 'admin':
        if user_to_update == request.user:
            pass
        elif user_to_update.role == 'manager' and user_to_update.created_by == request.user:
            pass
        else:
            messages.error(request, "Vous n'avez pas la permission de modifier cet utilisateur.")
            return redirect('account:dashboard')
    else:
        if user_to_update != request.user:
            messages.error(request, "Vous n'avez pas la permission de modifier cet utilisateur.")
            return redirect('account:dashboard')

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()

    if not first_name or not last_name:
        messages.error(request, 'Le prénom et le nom sont obligatoires.')
        return redirect('account:user_detail', user_uuid=user_uuid)

    user_to_update.first_name = first_name
    user_to_update.last_name = last_name
    user_to_update.save(update_fields=['first_name', 'last_name', 'updated_at'])
    messages.success(request, "Les informations de l'utilisateur ont été modifiées.")
    return redirect('account:user_detail', user_uuid=user_uuid)


@admin_required
def update_manager_station_view(request, user_uuid):
    """
    Met à jour la station gérée par un manager.
    Accessible aux admins/super_admins avec vérification de propriété.
    """
    if request.method != 'POST':
        return redirect('account:user_detail', user_uuid=user_uuid)

    manager_user = get_object_or_404(CustomUser, user_uuid=user_uuid, role='manager')

    if request.user.role == 'admin' and manager_user.created_by != request.user:
        messages.error(request, "Vous n'avez pas la permission de modifier ce gérant.")
        return redirect('account:managers_list')

    station_id = request.POST.get('station_id', '').strip()
    if not station_id:
        messages.error(request, "Veuillez sélectionner une station.")
        return redirect('account:user_detail', user_uuid=user_uuid)

    from stations.models import Station, StationManager
    if request.user.role == 'super_admin':
        station = Station.objects.filter(id=station_id).first()
    else:
        station = Station.objects.filter(id=station_id, owner=request.user).first()

    if not station:
        messages.error(request, "Station invalide.")
        return redirect('account:user_detail', user_uuid=user_uuid)

    StationManager.objects.update_or_create(
        manager=manager_user,
        defaults={'station': station},
    )
    messages.success(request, f'Station du gérant {manager_user.get_full_name()} mise à jour avec succès.')
    return redirect('account:user_detail', user_uuid=user_uuid)
