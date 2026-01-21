# apps/translations/services/exceptions.py

class TranslationError(Exception):
    """Base translation exception."""


class EmptySourceTextError(TranslationError):
    """Raised when source text is empty."""


class TranslationNotAllowedError(TranslationError):
    """Raised when translation is not permitted."""
