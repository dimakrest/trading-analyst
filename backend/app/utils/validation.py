"""Symbol validation utilities."""

MAX_SYMBOL_LENGTH = 10


def is_valid_symbol(symbol: str) -> bool:
    """
    Validate stock/index symbol format.

    Allows:
    - Alphanumeric characters (A-Z, 0-9)
    - Periods (.) for class shares (e.g., BRK.B)
    - Hyphens (-) for some tickers
    - Caret (^) for index symbols (e.g., ^VIX, ^GSPC)

    Args:
        symbol: The symbol to validate (should already be uppercase/stripped)

    Returns:
        True if symbol format is valid, False otherwise
    """
    if len(symbol) > MAX_SYMBOL_LENGTH:
        return False
    # Remove allowed special characters and check if remainder is alphanumeric
    cleaned = symbol.replace("^", "").replace(".", "").replace("-", "")
    return cleaned.isalnum()


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a symbol to uppercase and stripped.

    Args:
        symbol: The symbol to normalize

    Returns:
        Uppercase, stripped symbol
    """
    return symbol.upper().strip()
