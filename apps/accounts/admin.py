from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


# UserAdmin do Django já traz os formulários de senha (hash) e de permissões.
@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    pass
