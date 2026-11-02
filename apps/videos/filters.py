import django_filters

from apps.videos.models import Video


class VideoFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Video.Status.choices)
    visibility = django_filters.ChoiceFilter(choices=Video.Visibility.choices)
    # distinct: o JOIN com o ManyToMany repetiria linhas.
    tag = django_filters.CharFilter(field_name="tags__name", distinct=True)
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    mine = django_filters.BooleanFilter(method="filter_mine")

    class Meta:
        model = Video
        fields = ["status", "visibility", "tag", "created_after", "created_before", "mine"]

    def filter_mine(self, queryset, name, value):
        if value:
            return queryset.filter(owner=self.request.user)
        return queryset
