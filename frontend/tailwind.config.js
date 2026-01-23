/**
 * Tailwind CSS v4 Configuration
 *
 * ARCHITECTURE: CSS-First with @theme Directive
 * =============================================
 *
 * This project uses Tailwind v4's CSS-first configuration approach.
 * All design tokens are defined in `src/index.css` using the @theme directive,
 * NOT in this JavaScript config file.
 *
 * WHERE TOKENS ARE DEFINED:
 * - Colors:     @theme { --color-* }     → generates bg-*, text-*, border-* utilities
 * - Fonts:      @theme { --font-* }      → generates font-* utilities
 * - Font sizes: @theme { --text-* }      → generates text-* size utilities
 * - Shadows:    @theme { --shadow-* }    → generates shadow-* utilities
 * - Radius:     @theme { --radius-* }    → generates rounded-* utilities
 * - Spacing:    @theme { --spacing-* }   → generates w-*, p-*, gap-* utilities
 * - Animations: @theme { --animate-* }   → generates animate-* utilities
 *
 * WHY THIS APPROACH:
 * - Single source of truth for all design tokens (index.css)
 * - No duplication between CSS and JS config
 * - CSS variables work with both Tailwind utilities and custom CSS
 * - Easier to maintain and audit design system
 *
 * REFERENCES:
 * - Design tokens: src/index.css (@theme block, lines 160-270)
 * - Design system: docs/frontend/DESIGN_SYSTEM.md
 * - Tailwind docs: https://tailwindcss.com/docs/theme
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}
