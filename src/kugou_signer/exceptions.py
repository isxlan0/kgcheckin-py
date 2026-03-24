class KugouSignerError(Exception):
    """Base exception for the application."""


class ConfigError(KugouSignerError):
    """Raised when configuration is invalid."""


class ApiRequestError(KugouSignerError):
    """Raised when the remote KuGou API cannot be reached."""


class LoginTimeoutError(KugouSignerError):
    """Raised when QR login does not complete in time."""
