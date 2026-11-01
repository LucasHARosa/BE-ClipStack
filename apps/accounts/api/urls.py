# path() para os endpoints que não são ViewSet. O AdminUserViewSet é registrado no
# DefaultRouter central (config/api_v1.py).
from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.accounts.api.views import LoginView, MeView, RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    # refresh → novo access E novo refresh (rotação); o refresh usado vai para a blacklist.
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    # logout = pôr o refresh na blacklist. O access continua válido até expirar (15 min).
    path("auth/logout/", TokenBlacklistView.as_view(), name="auth-logout"),
    path("users/me/", MeView.as_view(), name="users-me"),
]
