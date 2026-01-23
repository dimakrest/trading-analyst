import { useEnvironment } from '@/contexts/EnvironmentContext';
import { cn } from '@/lib/utils';

interface EnvironmentBadgeProps {
  className?: string;
}

/**
 * Environment Badge
 *
 * Displays the current environment (DEV/PROD) with appropriate styling.
 * Uses the nav-env-badge CSS class for consistent Trading Terminal aesthetic.
 */
export function EnvironmentBadge({ className }: EnvironmentBadgeProps) {
  const { environment, isLoading } = useEnvironment();

  if (isLoading || environment === 'unknown') {
    return null;
  }

  const isDev = environment === 'development';

  return (
    <span
      className={cn(
        'nav-env-badge',
        // Override colors for production - use red for warning
        !isDev && 'bg-env-prod-muted text-env-prod border-env-prod/30',
        className
      )}
    >
      {isDev ? 'DEV' : 'PROD'}
    </span>
  );
}
