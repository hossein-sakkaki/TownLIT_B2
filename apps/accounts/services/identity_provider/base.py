# apps/accounts/services/identity_provider/base.py

from abc import ABC, abstractmethod


class BaseIdentityProvider(ABC):
    """
    Base abstraction for identity verification providers.
    """

    @abstractmethod
    def create_session(self, user, success_url=None, failure_url=None) -> dict:
        """
        Create a provider verification session.

        Must return a normalized shape:
        {
            "verification": {
                "id": "...",
                "url": "...",
                "status": "...",
                "raw": {...}
            }
        }
        """
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, raw_body: bytes, signature_header: str):
        """
        Verify webhook signature and return provider event/payload.
        Return None if invalid.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_webhook(self, event) -> dict:
        """
        Normalize provider webhook into common format:
        {
            "session_id": "...",
            "status": "...",
            "reason": "...",
            "risk": [...],
            "raw": {...}
        }
        """
        raise NotImplementedError