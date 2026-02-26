import { useEffect, useState } from 'react';

/**
 * Custom hook to detect responsive breakpoints with proper SSR support
 *
 * IMPORTANT: Always check `mounted` before rendering device-specific content
 * to prevent hydration mismatches.
 *
 * @returns {Object} Responsive state
 * @property {boolean} isMobile - True if viewport width < 768px
 * @property {boolean} isTablet - True if viewport width >= 768px and < 1024px
 * @property {boolean} isDesktop - True if viewport width >= 1024px
 * @property {string} breakpoint - Current breakpoint name ('mobile', 'tablet', 'desktop')
 * @property {boolean} mounted - True after client-side mount (prevents hydration mismatch)
 *
 * @example
 * ```tsx
 * const { isMobile, mounted } = useResponsive();
 *
 * // Prevent hydration mismatch
 * if (!mounted) return null;
 *
 * return isMobile ? <MobileView /> : <DesktopView />;
 * ```
 */
export const useResponsive = () => {
  const [mounted, setMounted] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    setMounted(true);

    // Define media queries matching Tailwind breakpoints
    const mobileQuery = window.matchMedia('(max-width: 767px)');
    const tabletQuery = window.matchMedia('(min-width: 768px) and (max-width: 1023px)');
    const desktopQuery = window.matchMedia('(min-width: 1024px)');

    const updateMatches = () => {
      setIsMobile(mobileQuery.matches);
      setIsTablet(tabletQuery.matches);
      setIsDesktop(desktopQuery.matches);
    };

    // Set initial values
    updateMatches();

    // Add event listeners for changes
    mobileQuery.addEventListener('change', updateMatches);
    tabletQuery.addEventListener('change', updateMatches);
    desktopQuery.addEventListener('change', updateMatches);

    // Cleanup
    return () => {
      mobileQuery.removeEventListener('change', updateMatches);
      tabletQuery.removeEventListener('change', updateMatches);
      desktopQuery.removeEventListener('change', updateMatches);
    };
  }, []);

  const breakpoint = isMobile ? 'mobile' : isTablet ? 'tablet' : 'desktop';

  return { isMobile, isTablet, isDesktop, breakpoint, mounted };
};
