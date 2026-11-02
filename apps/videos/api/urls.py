from django.urls import path

from apps.videos.api.views import CommentViewSet, DashboardStatsView, meta_view

# À mão: o DefaultRouter não gera rota aninhada.
comment_list = CommentViewSet.as_view({"get": "list", "post": "create"})
comment_detail = CommentViewSet.as_view({"delete": "destroy"})

urlpatterns = [
    path("meta/", meta_view, name="meta"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("videos/<int:video_pk>/comments/", comment_list, name="video-comments-list"),
    path("videos/<int:video_pk>/comments/<int:pk>/", comment_detail, name="video-comments-detail"),
]
