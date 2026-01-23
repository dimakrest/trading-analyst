import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { NAV_ITEMS, isNavItemActive } from './navigationConfig';

/**
 * Mobile Bottom Tabs Navigation
 *
 * Fixed bottom navigation for mobile devices (< 768px).
 * Features:
 * - All 4 navigation tabs with icons and labels
 * - Active state highlighting with accent-primary color
 * - Touch feedback with scale animation
 * - Safe area insets for devices with notches
 * - Hidden on desktop (md:hidden)
 * - Minimum 44px touch target height for accessibility
 */
export const MobileBottomTabs = () => {
  const location = useLocation();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-subtle bg-bg-secondary md:hidden"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      aria-label="Mobile navigation"
    >
      <div className="grid grid-cols-4 py-2 px-2 gap-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isNavItemActive(item.path, location.pathname);

          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex flex-col items-center justify-center gap-1 py-2 rounded-lg min-h-[44px] transition-all active:scale-95',
                active
                  ? 'text-accent-primary'
                  : 'text-text-muted hover:text-text-primary'
              )}
              aria-current={active ? 'page' : undefined}
            >
              <Icon
                className={cn(
                  'w-[22px] h-[22px]',
                  active && 'stroke-[2.5]'
                )}
              />
              <span
                className={cn(
                  'text-[10px] font-medium uppercase tracking-[0.03em]',
                  active && 'font-semibold'
                )}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};
