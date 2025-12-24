# apps/sanctuary/services/edit_lock_mixin.py

from apps.sanctuary.services.protection import assert_can_update


# Mixin to block updates when Sanctuary protection is active -------------------
class SanctuaryEditLockMixin:
    """
    Blocks update/partial_update when Sanctuary protection is active.
    - Delete is allowed (no override for destroy).
    """

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        assert_can_update(obj)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        assert_can_update(obj)
        return super().partial_update(request, *args, **kwargs)
