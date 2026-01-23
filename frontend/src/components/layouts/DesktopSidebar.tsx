import { Link, useLocation } from 'react-router-dom';
import { TrendingUp } from 'lucide-react';
import { EnvironmentBadge } from '@/components/EnvironmentBadge';
import { cn } from '@/lib/utils';
import { NAV_ITEMS, isNavItemActive } from './navigationConfig';

/**
 * Desktop Sidebar Navigation
 *
 * Vertical sidebar navigation for desktop (>= 768px).
 * Features:
 * - Gradient logo with TrendingUp icon
 * - Inline environment badge in header
 * - Refined nav link styling with rounded-md (--radius-md: 10px)
 * - Active state with accent-primary-muted background
 * - Hidden on mobile (hidden md:flex)
 */
export const DesktopSidebar = () => {
  const location = useLocation();

  return (
    <aside
      className="hidden md:flex md:w-60 flex-col border-r border-subtle bg-bg-secondary h-screen sticky top-0"
      aria-label="Desktop navigation"
    >
      {/* Header with gradient logo and inline environment badge */}
      <div className="flex items-center gap-3 p-5 border-b border-subtle">
        <div className="w-9 h-9 rounded-md nav-logo-gradient flex items-center justify-center">
          <TrendingUp className="w-5 h-5 text-white" />
        </div>
        <span className="font-display font-semibold text-base text-text-primary">
          Trading Analyst
        </span>
        <EnvironmentBadge className="ml-auto" />
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4" aria-label="Main navigation">
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isNavItemActive(item.path, location.pathname);

            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={cn(
                    'flex items-center gap-3 px-4 py-3 rounded-md text-sm font-medium transition-all duration-200',
                    active
                      ? 'bg-accent-primary-muted text-accent-primary'
                      : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
                  )}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon
                    className={cn('h-5 w-5', active && 'stroke-[2.5]')}
                  />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
};
