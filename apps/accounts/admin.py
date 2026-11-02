from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from apps.core.admin import ModerationAdminMixin

from .models import User


class ClipStackUserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "username")


class ClipStackUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(ModerationAdminMixin, DjangoUserAdmin):
    # Mudar role é pela API (set-role), que passa pelo service.
    form = ClipStackUserChangeForm
    add_form = ClipStackUserCreationForm

    list_display = ("email", "username", "role", "is_staff", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("email", "username")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Papel", {"fields": ("role", "is_staff")}),
        ("Status", {"fields": ("is_active", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2")}),
    )
    # is_staff é derivado do role no User.save().
    readonly_fields = ("is_staff", "last_login", "date_joined")
