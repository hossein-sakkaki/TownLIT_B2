from rest_framework.pagination import PageNumberPagination

class ConfigurablePagination(PageNumberPagination):
    """
    A general-purpose pagination class that allows
    page_size and max_page_size to be set dynamically.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def __init__(self, page_size=None, max_page_size=None):
        if page_size is not None:
            self.page_size = page_size
        if max_page_size is not None:
            self.max_page_size = max_page_size
