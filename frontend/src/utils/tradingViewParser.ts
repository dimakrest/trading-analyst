export interface ParsedWatchlist {
  /** Name from ###header### or empty string when absent (user must fill in) */
  name: string;
  symbols: string[];
}

/**
 * Matches a valid ticker symbol after stripping the exchange prefix.
 *
 * Allows:
 *  - Letters, digits, dots, and hyphens (covers BRK.B, BF.A, 3M → MMM edge aside,
 *    A2M, RDS.A, BRK-B, etc.)
 *  - 1–10 characters total
 *  - Must start with a letter or digit
 */
const SYMBOL_RE = /^[A-Z0-9][A-Z0-9.\-]{0,9}$/;

/**
 * Parse a TradingView exported watchlist file.
 *
 * Handles two formats:
 *   1. With header:  "###My List###\nNASDAQ:AAPL,NYSE:MSFT,..."
 *   2. Without header (most exports): "NASDAQ:AAPL,NYSE:MSFT,..."
 *
 * Tokens may be comma- or space-separated; exchange prefixes are stripped.
 * Invalid tokens (URLs, freeform notes) are silently ignored.
 *
 * Returns null only when no recognisable symbols are found at all.
 */
export const parseTradingViewFile = (text: string): ParsedWatchlist | null => {
  const lines = text.trim().split('\n').filter(Boolean);
  if (lines.length === 0) return null;

  let name = '';
  let symbolLines = lines;

  const header = lines[0].match(/^###(.+)###$/);
  if (header) {
    name = header[1].trim();
    symbolLines = lines.slice(1);
  }

  const symbols = [
    ...new Set(
      symbolLines
        .join(',')
        .split(/[,\s]+/)
        .map((token) => {
          // Strip exchange prefix (e.g. "NASDAQ:AAPL" → "AAPL")
          const afterColon = token.split(':').pop()!.trim().toUpperCase();
          return afterColon;
        })
        .filter((s) => s.length > 0 && SYMBOL_RE.test(s))
    ),
  ];

  if (symbols.length === 0) return null;
  return { name, symbols };
};
