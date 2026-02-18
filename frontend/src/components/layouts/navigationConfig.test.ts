import { describe, it, expect } from 'vitest';
import {
  NAV_ITEMS,
  MOBILE_NAV_ITEMS,
  MORE_NAV_ITEMS,
  isNavItemActive,
  isMoreMenuActive,
} from './navigationConfig';

describe('navigationConfig', () => {
  describe('NAV_ITEMS', () => {
    it('contains all 5 navigation items', () => {
      expect(NAV_ITEMS).toHaveLength(5);
    });

    it('contains Analysis as first item', () => {
      expect(NAV_ITEMS[0].path).toBe('/');
      expect(NAV_ITEMS[0].label).toBe('Analysis');
    });

    it('contains Live 20 as second item', () => {
      expect(NAV_ITEMS[1].path).toBe('/live-20');
      expect(NAV_ITEMS[1].label).toBe('Live 20');
    });

    it('contains Arena as third item', () => {
      expect(NAV_ITEMS[2].path).toBe('/arena');
      expect(NAV_ITEMS[2].label).toBe('Arena');
    });

    it('contains Agents as fourth item', () => {
      expect(NAV_ITEMS[3].path).toBe('/agents');
      expect(NAV_ITEMS[3].label).toBe('Agents');
    });

    it('contains Lists as fifth item', () => {
      expect(NAV_ITEMS[4].path).toBe('/lists');
      expect(NAV_ITEMS[4].label).toBe('Lists');
    });

    it('each item has an icon component', () => {
      NAV_ITEMS.forEach((item) => {
        expect(item.icon).toBeDefined();
        // Lucide icons are React forward ref components (objects with $$typeof)
        expect(item.icon).toHaveProperty('$$typeof');
      });
    });
  });

  describe('MOBILE_NAV_ITEMS', () => {
    it('contains all 3 navigation items', () => {
      expect(MOBILE_NAV_ITEMS).toHaveLength(3);
    });

    it('includes Analysis, Live 20, and Arena', () => {
      expect(MOBILE_NAV_ITEMS[0].label).toBe('Analysis');
      expect(MOBILE_NAV_ITEMS[1].label).toBe('Live 20');
      expect(MOBILE_NAV_ITEMS[2].label).toBe('Arena');
    });
  });

  describe('MORE_NAV_ITEMS', () => {
    it('contains two additional navigation items (Agents, Lists)', () => {
      expect(MORE_NAV_ITEMS).toHaveLength(2);
    });

    it('includes Agents as first item', () => {
      expect(MORE_NAV_ITEMS[0].label).toBe('Agents');
      expect(MORE_NAV_ITEMS[0].path).toBe('/agents');
    });

    it('includes Lists as second item', () => {
      expect(MORE_NAV_ITEMS[1].label).toBe('Lists');
      expect(MORE_NAV_ITEMS[1].path).toBe('/lists');
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

  describe('isMoreMenuActive', () => {
    it('returns false when on main navigation paths', () => {
      expect(isMoreMenuActive('/')).toBe(false);
      expect(isMoreMenuActive('/live-20')).toBe(false);
      expect(isMoreMenuActive('/arena')).toBe(false);
      expect(isMoreMenuActive('/stock/AAPL')).toBe(false);
    });

    it('returns true when on agents path', () => {
      expect(isMoreMenuActive('/agents')).toBe(true);
    });

    it('returns true when on lists path', () => {
      expect(isMoreMenuActive('/lists')).toBe(true);
    });
  });
});
