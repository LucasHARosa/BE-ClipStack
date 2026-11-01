"""Paginações da API."""

from rest_framework.pagination import CursorPagination, PageNumberPagination


class DefaultPagination(PageNumberPagination):
    # PageNumberPagination (?page=2&page_size=50): o padrão global. Dá "count" total e salto
    # direto para qualquer página, bom para listas com paginação numerada (vídeos, usuários).
    # Custo: um COUNT(*) por requisição e OFFSET, que fica lento em páginas muito altas.
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NewestFirstCursorPagination(CursorPagination):
    # CursorPagination (?cursor=<opaco>): para feeds que mudam o tempo todo (notificações).
    # Usa "WHERE created_at < <posição do cursor>" em vez de OFFSET: não repete nem pula itens
    # quando chegam novos registros e é rápido em qualquer profundidade. Em troca, não tem
    # contagem total nem salto para a página N; só "próxima" e "anterior".
    # Exige uma ordenação estável; "-id" desempata registros com o mesmo created_at.
    page_size = 20
    ordering = ("-created_at", "-id")
