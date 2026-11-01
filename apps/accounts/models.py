from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    # User customizado criado ANTES da primeira migration, mesmo vazio: assim os campos
    # (email de login, role) podem ser adicionados depois com uma migration simples.
    # Trocar AUTH_USER_MODEL com o banco já criado obriga a refazer as tabelas e as FKs.
    pass
