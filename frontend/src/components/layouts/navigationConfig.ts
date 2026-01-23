import type { ComponentType } from 'react';
import { LayoutDashboard, Search, List, Swords } from 'lucide-react';

/**
 * Navigation Item Interface
 */
export interface NavItem {
  path: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

/**
 * Shared Navigation Items
 * Used by both mobile bottom tabs and desktop sidebar
 */
export const NAV_ITEMS: NavItem[] = [
  {
    path: '/',
    label: 'Analysis',
    icon: LayoutDashboard,
  },
  {
    path: '/live-20',
    label: 'Live 20',
    icon: Search,
  },
  {
    path: '/arena',
    label: 'Arena',
    icon: Swords,
  },
  {
    path: '/lists',
    label: 'Lists',
    icon: List,
  },
];

/**
 * Mobile navigation items (first 3 items for bottom tabs)
 * The 4th tab will be "More" which opens a sheet with remaining items
 */
export const MOBILE_NAV_ITEMS = NAV_ITEMS.slice(0, 3);

/**
 * Items shown in the "More" menu sheet on mobile
 * These are the items that don't fit in the bottom tabs
 */
export const MORE_NAV_ITEMS = NAV_ITEMS.slice(3);

/**
 * Determines if a navigation item is active based on current pathname
 *
 * @param path - The navigation item's path
 * @param currentPathname - The current location pathname
 * @returns True if the nav item should be highlighted as active
 */
export const isNavItemActive = (path: string, currentPathname: string): boolean => {
  if (path === '/') {
    // For root path, check exact match or /stock/:symbol
    return currentPathname === '/' || currentPathname.startsWith('/stock/');
  }
  // For other paths, match if current path starts with the nav path
  return currentPathname.startsWith(path);
};

/**
 * Determines if any item in the "More" menu is currently active
 *
 * @param currentPathname - The current location pathname
 * @returns True if any "More" menu item should be highlighted
 */
export const isMoreMenuActive = (currentPathname: string): boolean => {
  return MORE_NAV_ITEMS.some((item) => isNavItemActive(item.path, currentPathname));
};
