# apps/core/square/stream/dto.py

class StreamItem:
    def __init__(self, *, kind: str, obj):
        self.kind = kind
        self.obj = obj
        self.id = obj.id
        self.published_at = obj.published_at
