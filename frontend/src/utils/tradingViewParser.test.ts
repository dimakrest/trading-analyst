import { describe, it, expect } from 'vitest';
import { parseTradingViewFile } from './tradingViewParser';

describe('parseTradingViewFile', () => {
  describe('header parsing', () => {
    it('extracts name from ###header### format', () => {
      const result = parseTradingViewFile('###My Watchlist###\nNASDAQ:AAPL,NYSE:MSFT');
      expect(result).not.toBeNull();
      expect(result!.name).toBe('My Watchlist');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT']);
    });

    it('trims whitespace in header name', () => {
      const result = parseTradingViewFile('###  Tech Stocks  ###\nAAPL');
      expect(result!.name).toBe('Tech Stocks');
    });

    it('returns empty name when no header present', () => {
      const result = parseTradingViewFile('NASDAQ:AAPL,NYSE:MSFT');
      expect(result!.name).toBe('');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT']);
    });
  });

  describe('exchange prefix stripping', () => {
    it('strips NASDAQ: prefix', () => {
      const result = parseTradingViewFile('NASDAQ:AAPL');
      expect(result!.symbols).toEqual(['AAPL']);
    });

    it('strips NYSE: prefix', () => {
      const result = parseTradingViewFile('NYSE:BRK.B');
      expect(result!.symbols).toEqual(['BRK.B']);
    });

    it('strips AMEX: prefix', () => {
      const result = parseTradingViewFile('AMEX:SPY');
      expect(result!.symbols).toEqual(['SPY']);
    });

    it('handles symbols without exchange prefix', () => {
      const result = parseTradingViewFile('AAPL,MSFT,GOOGL');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    });
  });

  describe('dot-containing tickers', () => {
    it('preserves BRK.B', () => {
      const result = parseTradingViewFile('NYSE:BRK.B,NYSE:BRK.A');
      expect(result!.symbols).toContain('BRK.B');
      expect(result!.symbols).toContain('BRK.A');
    });

    it('preserves BF.A and BF.B', () => {
      const result = parseTradingViewFile('BF.A,BF.B');
      expect(result!.symbols).toEqual(['BF.A', 'BF.B']);
    });
  });

  describe('digit-containing tickers', () => {
    it('preserves tickers with digits like A2M', () => {
      const result = parseTradingViewFile('A2M,3PL');
      expect(result!.symbols).toContain('A2M');
      expect(result!.symbols).toContain('3PL');
    });
  });

  describe('separators', () => {
    it('handles comma-separated symbols', () => {
      const result = parseTradingViewFile('AAPL,MSFT,GOOGL');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    });

    it('handles space-separated symbols', () => {
      const result = parseTradingViewFile('AAPL MSFT GOOGL');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    });

    it('handles mixed comma and space separators', () => {
      const result = parseTradingViewFile('AAPL, MSFT  GOOGL,NVDA');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL', 'NVDA']);
    });

    it('handles newline-separated symbols', () => {
      const result = parseTradingViewFile('AAPL\nMSFT\nGOOGL');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    });
  });

  describe('deduplication', () => {
    it('removes duplicate symbols', () => {
      const result = parseTradingViewFile('AAPL,MSFT,AAPL,GOOGL,MSFT');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT', 'GOOGL']);
    });

    it('deduplicates across exchange prefixes', () => {
      const result = parseTradingViewFile('NASDAQ:AAPL,NYSE:AAPL');
      expect(result!.symbols).toEqual(['AAPL']);
    });
  });

  describe('edge cases', () => {
    it('returns null for empty string', () => {
      expect(parseTradingViewFile('')).toBeNull();
    });

    it('returns null for whitespace-only string', () => {
      expect(parseTradingViewFile('   \n  \n  ')).toBeNull();
    });

    it('returns null when no valid symbols found', () => {
      expect(parseTradingViewFile('###Empty List###')).toBeNull();
    });

    it('filters out invalid tokens like URLs', () => {
      const result = parseTradingViewFile('AAPL,https://example.com,MSFT');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT']);
    });

    it('converts lowercase to uppercase', () => {
      const result = parseTradingViewFile('aapl,msft');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT']);
    });

    it('filters out tokens exceeding 10 characters', () => {
      const result = parseTradingViewFile('AAPL,VERYLONGSYMBOLNAME,MSFT');
      expect(result!.symbols).toEqual(['AAPL', 'MSFT']);
    });
  });
});
