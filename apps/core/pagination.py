# apps/core/pagination.py
from rest_framework.pagination import PageNumberPagination, CursorPagination


class _ViewAwarePageSizeMixin:
    """
    Allows setting page size per-view without coupling pagination to any action.

    How to use:
      - In any ViewSet (or APIView) set:
          pagination_page_size = 12
        OR
          page_size = 12

      - If not set, falls back to pagination class defaults.
    """

    def _get_view_page_size(self, request):
        ctx = getattr(request, "parser_context", None) or {}
        view = ctx.get("view", None)
        if not view:
            return None

        # Prefer explicit name (clear intent)
        size = getattr(view, "pagination_page_size", None)
        if size is None:
            size = getattr(view, "page_size", None)

        try:
            size = int(size) if size is not None else None
        except (TypeError, ValueError):
            return None

        if size is not None and size > 0:
            return size

        return None


# A general-purpose pagination class ---------------------------------------------------
class ConfigurablePagination(_ViewAwarePageSizeMixin, PageNumberPagination):
    """
    Page-number pagination with dynamic page size:
      - Default page_size = 20
      - Can be overridden per view via:
          pagination_page_size = 12  (recommended)
        or
          page_size = 12
      - Still supports ?page_size=... (if you want), capped by max_page_size
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        view_size = self._get_view_page_size(request)
        if view_size is not None:
            return min(view_size, self.max_page_size)
        return super().get_page_size(request)


# Instagram-like cursor pagination for feeds -------------------------------------------
class FeedCursorPagination(_ViewAwarePageSizeMixin, CursorPagination):
    """
    Cursor pagination with dynamic page size:
      - Default page_size = 20
      - Can be overridden per view via:
          pagination_page_size = 12  (recommended)
        or
          page_size = 12
    """
    page_size = 20

    # deterministic ordering
    ordering = ("-published_at", "-id")

    cursor_query_param = "cursor"
    page_size_query_param = None
    max_page_size = 50

    def get_page_size(self, request):
        view_size = self._get_view_page_size(request)
        if view_size is not None:
            return min(view_size, self.max_page_size)
        return super().get_page_size(request)
