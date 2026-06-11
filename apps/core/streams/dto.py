# apps/core/streams/dto.py

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamItem:
    """
    Normalized stream item wrapper.
    """

    kind: str
    obj: object

    @property
    def id(self):
        return self.obj.id

    @property
    def published_at(self):
        return self.obj.published_at


@dataclass(frozen=True)
class StreamPage:
    """
    Final stream page result.
    """

    items: list[StreamItem]
    next_cursor: str | None
    kind: str
    subtype: str
    scope: str
    mode: str
    extension: int
    can_continue: bool
    limit_reached: bool = False
    
    
