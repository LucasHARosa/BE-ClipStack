from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from apps.accounts.api.views import LoginView, MeView, RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    # O access continua válido até expirar.
    path("auth/logout/", TokenBlacklistView.as_view(), name="auth-logout"),
    path("users/me/", MeView.as_view(), name="users-me"),
]
