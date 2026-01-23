/**
 * PageBackground Component
 *
 * Renders a subtle grid pattern background for the Trading Terminal aesthetic.
 * Uses the indigo accent color at very low opacity to create depth.
 *
 * Features:
 * - Fixed positioning to cover entire viewport
 * - Pointer-events disabled for click-through
 * - Z-index 0 to stay behind all content
 * - 60px grid spacing matching the design system
 */
export function PageBackground() {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0"
      style={{
        backgroundImage: `
          linear-gradient(rgba(99, 102, 241, 0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(99, 102, 241, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }}
      aria-hidden="true"
    />
  );
}
