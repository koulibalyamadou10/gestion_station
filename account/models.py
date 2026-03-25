from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings
import uuid

# Create your models here.
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if email:
            email = self.normalize_email(email)
        else:
            email = None

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Propriétaire d\'une station-service'),
        ('manager', 'Gérant d\'une station-service'),
    ]
    
    user_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True, editable=False)
    first_name = models.CharField(max_length=50,blank=False,null=False )
    last_name = models.CharField(max_length=50,blank=False, null=False)
    email = models.EmailField(
        blank=True,
        null=True,
        error_messages={
            'invalid': _("Veuillez entrer un mail valide"),
        },
        unique=True,
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Identifiant unique (affichage / référence)."),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="admin")
    phone_number = models.CharField(max_length=9,blank=False,null=False)
    phone_code = models.CharField(max_length=9, blank=False, null=False)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
    
    def get_short_name(self):
        return self.first_name

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.email} {self.role}"
    
    def send_credentials_email(self, password, login_url=None):
        """
        Envoie un email avec les identifiants de connexion à l'utilisateur
        
        Args:
            password: Le mot de passe généré à envoyer
            login_url: URL de connexion (optionnel)
        
        Returns:
            bool: True si l'email a été envoyé avec succès, False sinon
        """
        if not self.email:
            return False
        try:
            subject = 'Bienvenue sur Station Manager - Vos identifiants de connexion'
            
            # Construire l'URL de connexion si non fournie
            if not login_url:
                from django.contrib.sites.models import Site
                try:
                    current_site = Site.objects.get_current()
                    login_url = f"https://{current_site.domain}/login/"
                except:
                    login_url = "/login/"
            
            message = f"""Bonjour {self.get_full_name()},

Votre compte a été créé avec succès sur la plateforme Station Manager.

Voici vos identifiants de connexion :

📧 Email : {self.email}
🔑 Mot de passe : {password}

⚠️ IMPORTANT : Pour des raisons de sécurité, nous vous recommandons fortement de changer ce mot de passe lors de votre première connexion.

Vous pouvez vous connecter en visitant : {login_url}

Cordialement,
L'équipe Station Manager"""
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            # Logger l'erreur si nécessaire
            print(f"Erreur lors de l'envoi de l'email à {self.email}: {str(e)}")
            return False