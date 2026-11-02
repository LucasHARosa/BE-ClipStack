from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NewestFirstCursorPagination(CursorPagination):
    # Cursor em vez de OFFSET: não repete nem pula itens quando chegam registros novos.
    # "-id" desempata registros com o mesmo created_at.
    page_size = 20
    ordering = ("-created_at", "-id")
