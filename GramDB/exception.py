"""
GramDB Custom Exceptions.

Defines the core exception classes used across the GramDB library and its 
interactions with Telegram and the Registry API.
"""


class GramDBError(Exception):
    """Base class for GramDB errors."""

    pass


class GramDBConnectionError(GramDBError):
    """Registry or network connectivity failure."""

    pass


class GramDBAuthError(GramDBError):
    """Invalid database URL, token, or registry response."""

    pass


class GramDBSessionConflictError(GramDBError):
    """Another live GramDB client already holds the singleton session lease."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details


class GramDBTelegramError(GramDBError):
    """Telegram / Pyrogram operation failure (permissions, channel, flood, etc.)."""

    pass


class GramDBNotFoundError(GramDBError):
    """Missing table or record."""

    pass


class GramDBDuplicateTableError(GramDBError):
    """Table already exists."""

    pass


class GramDBValidationError(GramDBError):
    """Payload or schema validation error."""

    pass


class GramDBIndexTooLargeError(GramDBError):
    """Catalog JSON no longer fits in a single Telegram message."""

    pass
