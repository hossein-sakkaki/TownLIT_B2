# apps/accounts/services/identity_provider/factory.py

from django.conf import settings

from .stripe_provider import StripeIdentityProvider


def get_identity_provider():
    """
    Return the configured identity provider.
    """
    provider_name = getattr(settings, "IDENTITY_PROVIDER", "stripe").lower()

    if provider_name == "stripe":
        return StripeIdentityProvider()

    raise RuntimeError(f"Unsupported identity provider: {provider_name}")