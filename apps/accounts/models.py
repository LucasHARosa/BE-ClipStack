from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "USER", "Usuário"
        ADMIN = "ADMIN", "Administrador"

    email = models.EmailField("email", unique=True)
    role = models.CharField("papel", max_length=10, choices=Role.choices, default=Role.USER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # role é a fonte da verdade; is_staff é derivado. QuerySet.update() pula isto.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        self.is_staff = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN
