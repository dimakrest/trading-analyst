import { useState, useRef, useCallback, type ReactNode } from 'react';
import { Progress } from './progress';

interface PullToRefreshProps {
  onRefresh: () => Promise<void>;
  children: ReactNode;
  threshold?: number;
  disabled?: boolean;
}

export const PullToRefresh = ({
  onRefresh,
  children,
  threshold = 80,
  disabled = false
}: PullToRefreshProps) => {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [canPull, setCanPull] = useState(true);

  const touchStartY = useRef<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const isPulling = useRef<boolean>(false);

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (disabled || isRefreshing) return;

      // Only allow pull-to-refresh when scrolled to the top
      const container = containerRef.current;
      if (container && container.scrollTop === 0) {
        touchStartY.current = e.touches[0].clientY;
        isPulling.current = true;
        setCanPull(true);
      } else {
        setCanPull(false);
      }
    },
    [disabled, isRefreshing]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (disabled || isRefreshing || !canPull || !isPulling.current) return;

      const currentY = e.touches[0].clientY;
      const distance = currentY - touchStartY.current;

      // Only pull down (positive distance)
      if (distance > 0) {
        // Apply resistance effect: diminishing returns as you pull further
        const resistance = 0.5;
        const adjustedDistance = Math.min(distance * resistance, threshold * 1.5);

        setPullDistance(adjustedDistance);

        // Prevent default scrolling when pulling
        if (adjustedDistance > 5) {
          e.preventDefault();
        }
      }
    },
    [disabled, isRefreshing, canPull, threshold]
  );

  const handleTouchEnd = useCallback(
    async () => {
      if (disabled || isRefreshing || !isPulling.current) return;

      isPulling.current = false;

      // If pulled past threshold, trigger refresh
      if (pullDistance >= threshold) {
        setIsRefreshing(true);
        try {
          await onRefresh();
        } finally {
          setIsRefreshing(false);
          setPullDistance(0);
        }
      } else {
        // Animate back to 0
        setPullDistance(0);
      }
    },
    [disabled, isRefreshing, pullDistance, threshold, onRefresh]
  );

  // Calculate progress percentage
  const progressPercentage = Math.min((pullDistance / threshold) * 100, 100);

  // Determine text based on state
  let statusText = '';
  if (isRefreshing) {
    statusText = 'Refreshing...';
  } else if (pullDistance >= threshold) {
    statusText = 'Release to refresh';
  } else if (pullDistance > 0) {
    statusText = 'Pull to refresh';
  }

  return (
    <div
      ref={containerRef}
      className="relative h-full overflow-auto"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Pull-to-refresh indicator */}
      <div
        className="absolute top-0 left-0 right-0 flex flex-col items-center justify-center transition-all duration-200 ease-out z-50"
        style={{
          height: `${pullDistance}px`,
          opacity: pullDistance > 0 ? 1 : 0,
        }}
      >
        <div className="flex flex-col items-center gap-2 pb-2">
          {/* Progress ring */}
          <div className="w-8 h-8 relative">
            <Progress
              value={progressPercentage}
              className="h-2"
            />
          </div>

          {/* Status text */}
          {statusText && (
            <span className="text-xs text-muted-foreground font-medium">
              {statusText}
            </span>
          )}
        </div>
      </div>

      {/* Content with dynamic padding to prevent jump */}
      <div
        className="transition-transform duration-200 ease-out"
        style={{
          transform: `translateY(${pullDistance}px)`,
        }}
      >
        {children}
      </div>
    </div>
  );
};
