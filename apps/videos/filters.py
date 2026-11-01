"""FilterSets do django-filter: query params → filtros do QuerySet, com validação.

Os filtros são aplicados SOBRE o get_queryset() da view, então nunca ampliam o que o usuário
pode ver: só restringem.
"""

import django_filters

from apps.videos.models import Video


class VideoFilter(django_filters.FilterSet):
    # ?status=completed  → ChoiceFilter: valor fora das choices vira 400.
    status = django_filters.ChoiceFilter(choices=Video.Status.choices)
    visibility = django_filters.ChoiceFilter(choices=Video.Visibility.choices)
    # ?tag=vlog → JOIN com a tabela intermediária. distinct=True evita linhas repetidas
    # quando o filtro atravessa um ManyToMany.
    tag = django_filters.CharFilter(field_name="tags__name", distinct=True)
    # ?created_after=2026-01-01&created_before=2026-12-31 (inclusive, pela data)
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    # ?mine=true → só os vídeos do usuário logado (method= recebe o queryset e o valor).
    mine = django_filters.BooleanFilter(method="filter_mine")

    class Meta:
        model = Video
        fields = ["status", "visibility", "tag", "created_after", "created_before", "mine"]

    def filter_mine(self, queryset, name, value):
        if value:
            return queryset.filter(owner=self.request.user)
        return queryset
