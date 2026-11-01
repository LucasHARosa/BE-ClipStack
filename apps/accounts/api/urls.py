# path() para os endpoints que não são ViewSet. O AdminUserViewSet é registrado no
# DefaultRouter central (config/api_v1.py).
from django.urls import path

from apps.accounts.api.views import MeView, RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("users/me/", MeView.as_view(), name="users-me"),
]
