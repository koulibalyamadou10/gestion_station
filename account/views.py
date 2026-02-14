from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

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
