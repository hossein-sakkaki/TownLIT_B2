# apps/accounting/services/exceptions.py

class AccountingError(Exception):
    """Base accounting exception."""
    pass


class JournalEntryValidationError(AccountingError):
    """Raised when journal entry validation fails."""
    pass


class AccountNotFoundError(AccountingError):
    """Raised when an account code cannot be resolved."""
    pass