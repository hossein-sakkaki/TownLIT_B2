# apps/core/availability/interfaces.py

class AvailabilityAware:
    """
    Domain contract for objects that become available
    after async processes (e.g. media conversion).
    """

    def is_available(self) -> bool:
        """
        Return True when the object is fully usable by end users.
        """
        raise NotImplementedError

    def on_available(self):
        """
        Called exactly once when the object becomes available.
        """
        raise NotImplementedError
