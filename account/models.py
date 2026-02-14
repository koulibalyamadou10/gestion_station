from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _

# Create your models here.
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('You did not enter a valid email address.')

        email = self.normalize_email(email)
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
        ('super_admin', 'Super Administrateur'),
        ('admin', 'Propriétaire d\'une station-service'),
        ('manager', 'Gérant d\'une station-service'),
    ]
    
    first_name = models.CharField(max_length=50,blank=False,null=False )
    last_name = models.CharField(max_length=50,blank=False, null=False)
    email = models.EmailField(unique=True, blank=False,null=False, error_messages={
        'unique': _("Ce mail existe déja"),
        'required': _("Veuillez entrer un mail valide"),
        'blank': _("Veuillez entrer un mail valide"),
        'invalid': _("Veuillez entrer un mail valide"),
    })
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="super_admin")
    phone_number = models.CharField(max_length=9,blank=False,null=False)
    phone_code = models.CharField(max_length=9, blank=False, null=False)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

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