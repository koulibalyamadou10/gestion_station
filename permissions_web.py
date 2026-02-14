"""
Système de permissions basé sur les rôles pour les vues web.

Les rôles disponibles :
- super_admin : Super Administrateur (accès total)
- admin : Propriétaire d'une station-service
- manager : Gérant d'une station-service

Hiérarchie des permissions :
- super_admin : Accès à tout
- admin : Accès limité à ses stations et gérants
- manager : Accès limité à sa station assignée

Exemples d'utilisation :

1. Décorateur générique avec plusieurs rôles :
    @role_required('super_admin', 'admin')
    def ma_vue(request):
        # Accessible uniquement aux super_admins et admins
        return render(request, 'template.html')

2. Décorateurs spécifiques :
    @super_admin_required
    def vue_super_admin(request):
        # Accessible uniquement aux super_admins
        pass
    
    @admin_required
    def vue_admin(request):
        # Accessible aux super_admins et admins
        pass
    
    @manager_required
    def vue_manager(request):
        # Accessible à tous les rôles authentifiés
        pass

3. Combinaison avec d'autres décorateurs :
    @login_required
    @role_required('super_admin', 'admin')
    def vue_gestion(request):
        # Accessible aux super_admins et admins
        pass
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def role_required(*required_roles):
    """
    Décorateur pour vérifier que l'utilisateur a au moins un des rôles requis.
    
    Usage:
        @role_required('super_admin', 'admin')
        def ma_vue(request):
            ...
    
    Args:
        *required_roles: Un ou plusieurs rôles requis (ex: 'super_admin', 'admin', 'manager')
    
    Returns:
        Décorateur qui redirige vers 'not_access' si l'utilisateur n'a pas les permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='login')
        def wrapper(request, *args, **kwargs):
            # Vérifier si l'utilisateur est authentifié
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Les super_admins ont accès à tout
            if hasattr(request.user, 'role') and request.user.role == 'super_admin':
                return view_func(request, *args, **kwargs)
            
            # Vérifier si l'utilisateur a au moins un des rôles requis
            user_role = getattr(request.user, 'role', None)
            has_required_role = user_role in required_roles
            
            if not has_required_role:
                return redirect('not_access')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def super_admin_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est super administrateur.
    
    Usage:
        @super_admin_required
        def ma_vue(request):
            ...
    """
    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not hasattr(request.user, 'role') or request.user.role != 'super_admin':
            return redirect('not_access')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est admin ou super_admin.
    
    Usage:
        @admin_required
        def ma_vue(request):
            ...
    """
    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['super_admin', 'admin']:
            return redirect('not_access')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def manager_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est manager, admin ou super_admin.
    
    Usage:
        @manager_required
        def ma_vue(request):
            ...
    """
    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['super_admin', 'admin', 'manager']:
            return redirect('not_access')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_or_manager_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est admin ou manager (pas super_admin).
    
    Usage:
        @admin_or_manager_required
        def ma_vue(request):
            ...
    """
    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        user_role = getattr(request.user, 'role', None)
        if user_role not in ['admin', 'manager']:
            return redirect('not_access')
        
        return view_func(request, *args, **kwargs)
    return wrapper

