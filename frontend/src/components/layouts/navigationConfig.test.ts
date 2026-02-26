import { describe, it, expect } from 'vitest';
import {
  NAV_ITEMS,
  isNavItemActive,
} from './navigationConfig';

describe('navigationConfig', () => {
  describe('NAV_ITEMS', () => {
    it('contains 1 navigation item', () => {
      expect(NAV_ITEMS).toHaveLength(1);
    });

    it('contains Analysis as the only item', () => {
      expect(NAV_ITEMS[0].path).toBe('/');
      expect(NAV_ITEMS[0].label).toBe('Analysis');
    });

    it('each item has an icon component', () => {
      NAV_ITEMS.forEach((item) => {
        expect(item.icon).toBeDefined();
        // Lucide icons are React forward ref components (objects with $$typeof)
        expect(item.icon).toHaveProperty('$$typeof');
      });
    });
  });

  describe('isNavItemActive', () => {
    it('returns true for root path when pathname is /', () => {
      expect(isNavItemActive('/', '/')).toBe(true);
    });

    it('returns true for root path when pathname starts with /stock/', () => {
      expect(isNavItemActive('/', '/stock/AAPL')).toBe(true);
      expect(isNavItemActive('/', '/stock/TSLA')).toBe(true);
    });

    it('returns false for root path when pathname is different', () => {
      expect(isNavItemActive('/', '/live-20')).toBe(false);
      expect(isNavItemActive('/', '/lists')).toBe(false);
    });

    it('returns true when pathname starts with the nav path', () => {
      expect(isNavItemActive('/live-20', '/live-20')).toBe(true);
      expect(isNavItemActive('/live-20', '/live-20/history')).toBe(true);
      expect(isNavItemActive('/lists', '/lists')).toBe(true);
    });

    it('returns false when pathname does not start with nav path', () => {
      expect(isNavItemActive('/live-20', '/')).toBe(false);
      expect(isNavItemActive('/live-20', '/lists')).toBe(false);
      expect(isNavItemActive('/lists', '/live-20')).toBe(false);
    });
  });
});
