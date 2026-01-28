# apps/core/square/stream/interfaces.py

class StreamSubtypeResolver:
    """
    Resolve stream subtype for a model instance.

    This isolates model-specific logic and allows
    future models (Journey, Pray, etc.) to plug in cleanly.
    """

    @staticmethod
    def resolve(instance) -> str | None:
        """
        Must return one of STREAM_SUBTYPES or None.
        """
        raise NotImplementedError
