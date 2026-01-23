"""Core exception classes for the Trading Analyst application."""


class DataServiceError(Exception):
    """Base exception for data service operations."""

    pass


class APIError(DataServiceError):
    """Raised when external API operations fail."""

    pass


class DataValidationError(DataServiceError):
    """Raised when data validation fails."""

    pass


class SymbolNotFoundError(DataServiceError):
    """Raised when a stock symbol is not found."""

    pass
