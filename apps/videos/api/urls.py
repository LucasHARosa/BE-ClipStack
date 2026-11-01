# path() para os endpoints que não são ViewSet e para a rota aninhada de comentários.
# VideoViewSet e TagViewSet são registrados no DefaultRouter central (config/api_v1.py).
from django.urls import path

from apps.videos.api.views import CommentViewSet, DashboardStatsView, meta_view

# as_view({verbo: ação}): é exatamente o que o router faz por baixo. Aqui à mão porque a rota
# é aninhada (o DefaultRouter não gera /videos/{video_pk}/comments/).
comment_list = CommentViewSet.as_view({"get": "list", "post": "create"})
comment_detail = CommentViewSet.as_view({"delete": "destroy"})

urlpatterns = [
    path("meta/", meta_view, name="meta"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("videos/<int:video_pk>/comments/", comment_list, name="video-comments-list"),
    path("videos/<int:video_pk>/comments/<int:pk>/", comment_detail, name="video-comments-detail"),
]
