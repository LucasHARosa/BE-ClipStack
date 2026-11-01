from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    # Manager customizado: o createsuperuser cria o usuário já com role ADMIN.
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    # AbstractUser: herda username, senha (hash), is_staff, is_superuser, grupos e permissões.
    # (AbstractBaseUser seria a opção para começar do zero, sem username.)

    # TextChoices: enum do Django; grava "USER"/"ADMIN" no banco e expõe o rótulo legível.
    class Role(models.TextChoices):
        USER = "USER", "Usuário"
        ADMIN = "ADMIN", "Administrador"

    email = models.EmailField("email", unique=True)
    role = models.CharField("papel", max_length=10, choices=Role.choices, default=Role.USER)

    # USERNAME_FIELD: campo usado no login. REQUIRED_FIELDS: pedidos a mais no createsuperuser.
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        # db_table: nome da tabela explícito em vez do padrão "<app>_<model>" (accounts_user).
        db_table = "users"
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # role é a fonte da verdade; is_staff (acesso ao Django Admin) é derivado dele.
        # Sem essa sincronia, alguém poderia ser ADMIN na API sem conseguir abrir o Admin,
        # ou ter is_staff sem ser ADMIN (e ver dados que a API esconderia).
        # Atenção: QuerySet.update() não chama save(); mudanças de role passam pelo service.
        if self.is_superuser:
            self.role = self.Role.ADMIN
        self.is_staff = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)

    # @property: atributo calculado. As permissões checam request.user.is_admin, que vem do
    # banco (o objeto User carregado na autenticação), nunca do claim "role" do token.
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN
