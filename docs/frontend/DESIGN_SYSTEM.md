# Design System

This document establishes the unified design system for the Trading Analyst application. All frontend development must follow these standards to ensure consistency, accessibility, and a professional trading application experience.

---

## Quick Reference

### Color Utilities

| Category | Utilities |
|----------|-----------|
| **Backgrounds** | `bg-bg-primary`, `bg-bg-secondary`, `bg-bg-tertiary`, `bg-bg-elevated` |
| **Text** | `text-text-primary`, `text-text-secondary`, `text-text-muted` |
| **Accents** | `text-accent-bullish`, `text-accent-bearish`, `text-accent-primary` |
| **Borders** | `border-subtle`, `border-default` |
| **Signals** | `text-signal-long`, `text-signal-short`, `bg-signal-long-muted`, `bg-signal-short-muted` |
| **Indicators** | `text-up-indicator`, `text-down-indicator` |
| **Scores** | `text-score-high`, `text-score-medium`, `text-score-low` |
| **Environment** | `text-env-dev`, `text-env-prod`, `bg-env-dev-muted`, `bg-env-prod-muted` |

### Typography Utilities

| Role | Class | Usage |
|------|-------|-------|
| **Display** | `font-display` | Headers, stock symbols |
| **Body** | `font-sans` | UI labels, descriptions |
| **Data** | `font-mono` | All numbers, prices, timestamps |

---

## Foundation

The Trading Analyst UI is built on:
- **shadcn/ui**: High-quality components based on Radix UI primitives
- **Tailwind CSS v4**: Utility-first CSS with CSS-first configuration
- **Mobile-First Philosophy**: Design for 320px+, progressively enhance for larger screens
- **Trading Terminal Aesthetic**: Dark-first, information-dense, professional command center feel

### Visual Identity

- Deep space dark palette with layered backgrounds
- Distinctive typography pairing (display + data fonts)
- Border-based elevation instead of shadows
- Glow effects for emphasis on key data
- Subtle grid pattern for depth
- Live indicators with pulse animations

---

## Tailwind v4 CSS-First Architecture

This project uses Tailwind v4's **CSS-first configuration** approach. All design tokens are defined in `src/index.css` using the `@theme` directive, NOT in `tailwind.config.js`.

### Where Design Tokens Live

| Token Type | Namespace | Generates Utilities | Defined In |
|------------|-----------|---------------------|------------|
| Colors | `--color-*` | `bg-*`, `text-*`, `border-*` | `index.css` @theme |
| Fonts | `--font-*` | `font-*` | `index.css` @theme |
| Font Sizes | `--text-*` | `text-*` (sizes) | `index.css` @theme |
| Shadows | `--shadow-*` | `shadow-*` | `index.css` @theme |
| Border Radius | `--radius-*` | `rounded-*` | `index.css` @theme |
| Spacing | `--spacing-*` | `w-*`, `p-*`, `gap-*` | `index.css` @theme |
| Animations | `--animate-*` | `animate-*` | `index.css` @theme |

### Adding New Design Tokens

```css
/* ✅ Correct: Add to @theme in index.css */
@theme {
  --color-my-custom: #ff00ff;  /* Creates bg-my-custom, text-my-custom */
}

/* ❌ Wrong: Don't add to tailwind.config.js */
// theme: { extend: { colors: { ... } } }  // DON'T DO THIS
```

### Critical Rules

**Never use `dark:` classes:**

```tsx
// ❌ NEVER - Tailwind v4 uses OS-level prefers-color-scheme, not app state
<h2 className="text-gray-900 dark:text-white">Text</h2>

// ✅ ALWAYS - Use semantic color tokens
<h2 className="text-text-primary">Text</h2>
```

---

## Token Systems: Custom vs ShadCN

This project uses two overlapping token systems. Choose the right one for your context:

### Custom Trading Tokens (Preferred for Trading UI)

Use these for trading-specific interfaces:

| Token | Class | Usage |
|-------|-------|-------|
| `--text-primary` | `text-text-primary` | Primary text, headings |
| `--text-secondary` | `text-text-secondary` | Body text, descriptions |
| `--text-muted` | `text-text-muted` | Labels, placeholders |
| `--bg-primary` | `bg-bg-primary` | Page background |
| `--bg-secondary` | `bg-bg-secondary` | Cards, panels |
| `--accent-bullish` | `text-accent-bullish` | Profits, positive values |
| `--accent-bearish` | `text-accent-bearish` | Losses, negative values |

### ShadCN Tokens (For Component Library Compatibility)

Use these when working with shadcn/ui components or need component library compatibility:

| Token | Class | Equivalent Custom Token |
|-------|-------|------------------------|
| `--foreground` | `text-foreground` | `text-text-primary` |
| `--muted-foreground` | `text-muted-foreground` | `text-text-secondary` |
| `--background` | `bg-background` | `bg-bg-primary` |
| `--card` | `bg-card` | `bg-bg-secondary` |

**Rule of thumb**: Use custom tokens for new trading UI code. Use ShadCN tokens when extending or styling shadcn/ui components to maintain consistency with the component library.

---

## Typography

### Font Stack (3-Tier System)

| Role | Font | Weight | Usage |
|------|------|--------|-------|
| **Display** | Space Grotesk | 400-700 | Headers, stock symbols, page titles |
| **Body** | Inter | 400-600 | UI labels, descriptions, navigation |
| **Data** | JetBrains Mono | 400-700 | All numbers, prices, percentages, timestamps |

### Typography Scale

| Token | Size | Weight | Font | Usage |
|-------|------|--------|------|-------|
| `text-hero` | 48px | 700 | JetBrains Mono | Hero price display |
| `text-symbol` | 36px | 700 | Space Grotesk | Stock symbols in hero |
| `text-title` | 24px | 600 | Space Grotesk | Page titles |
| `text-heading` | 18-20px | 600 | Space Grotesk | Section headings |
| `text-price` | 16-18px | 600 | JetBrains Mono | Secondary prices |
| `text-body` | 14px | 400-500 | Inter | Body text, descriptions |
| `text-stat` | 13-14px | 600 | JetBrains Mono | Stat values, table data |
| `text-label` | 10-11px | 500-600 | Inter | Uppercase labels, captions |

### Typography Rules

**CRITICAL**: All numeric displays must use the data font (JetBrains Mono) with tabular numerics:

```tsx
// Correct - Data font for numbers
<span className="font-mono">$198.45</span>
<span className="font-mono">+2.34%</span>
<span className="font-mono">48.2M</span>

// Correct - Display font for symbols
<span className="font-display text-3xl font-bold">AAPL</span>

// Wrong - Body font for numbers
<span>$198.45</span>
```

The `font-mono` class automatically applies `font-variant-numeric: tabular-nums` for fixed-width numbers.

---

## Color System

### Design Philosophy

- **Dark Mode Primary**: All colors are designed for dark backgrounds first
- **Layered Backgrounds**: Depth through background layers, not shadows
- **Border-Based Elevation**: Subtle borders instead of drop shadows
- **Context-Aware Colors**: Different palettes for different contexts (P&L vs. signals)
- **WCAG Compliance**: All text meets minimum 4.5:1 contrast ratio

### Background Layers

Create visual hierarchy through background colors rather than shadows:

| Token | Hex | CSS Variable | Usage |
|-------|-----|--------------|-------|
| **Primary** | `#0a0b0f` | `--bg-primary` | Page background, deepest layer |
| **Secondary** | `#12141a` | `--bg-secondary` | Sidebars, cards, panels |
| **Tertiary** | `#1a1d24` | `--bg-tertiary` | Inputs, elevated surfaces |
| **Elevated** | `#22262f` | `--bg-elevated` | Hover states, active items |

```tsx
<body className="bg-bg-primary">
<aside className="bg-bg-secondary">
<input className="bg-bg-tertiary">
<div className="hover:bg-bg-elevated">
```

### Accent Colors

| Token | Hex | CSS Variable | Usage |
|-------|-----|--------------|-------|
| **Primary** | `#6366f1` | `--accent-primary` | UI accents, focus rings, active states |
| **Primary Muted** | `rgba(99,102,241,0.15)` | `--accent-primary-muted` | Active backgrounds |
| **Bullish** | `#00d26a` | `--accent-bullish` | Profits, positive values, bullish signals |
| **Bearish** | `#ff4757` | `--accent-bearish` | Losses, negative values, bearish signals |

```tsx
<button className="bg-accent-primary text-white">
<span className="text-accent-bullish">+$1,234</span>
<span className="text-accent-bearish">-$567</span>
```

### Text Colors

| Token | Hex | CSS Variable | Contrast | Usage |
|-------|-----|--------------|----------|-------|
| **Primary** | `#f8fafc` | `--text-primary` | 15.8:1 | Headings, primary content |
| **Secondary** | `#94a3b8` | `--text-secondary` | 7.2:1 | Body text, descriptions |
| **Muted** | `#64748b` | `--text-muted` | 4.6:1 | Labels, placeholders, captions |

```tsx
<h1 className="text-text-primary">Title</h1>
<p className="text-text-secondary">Description</p>
<label className="text-text-muted">Label</label>
```

### Border Colors

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| **Subtle** | `rgba(255,255,255,0.06)` | `--border-subtle` | Subtle separators, section dividers |
| **Default** | `rgba(255,255,255,0.1)` | `--border-default` | Standard borders, card outlines |

```tsx
<aside className="border-r border-subtle">
<div className="border border-default rounded-lg">
```

### Trading-Specific Colors

Different contexts use different color palettes to reduce confusion and alarm fatigue:

#### Position P&L (High Importance)
Use when displaying actual money gained/lost:

| State | Color | Token | Usage |
|-------|-------|-------|-------|
| Profit | `#00d26a` | `accent-bullish` | Positive P&L values |
| Loss | `#ff4757` | `accent-bearish` | Negative P&L values |

#### Screener Signals (Analytical)
Use for analysis and recommendations (reduced alarm fatigue):

| State | Color | Token | Muted Variant | Usage |
|-------|-------|-------|---------------|-------|
| Long | Teal `#14b8a6` | `signal-long` | `signal-long-muted` | Long position signals |
| Short | Orange `#f97316` | `signal-short` | `signal-short-muted` | Short position signals |

#### Technical Indicators (Neutral)
Use for directional information without financial implication:

| State | Color | Token | Usage |
|-------|-------|-------|-------|
| Up | Blue `hsl(220 70% 50%)` | `up-indicator` | Upward movement (CCI rising, etc.) |
| Down | Purple `hsl(280 65% 55%)` | `down-indicator` | Downward movement (CCI falling, etc.) |

#### Score/Rating Colors
Use for confidence scores and ratings:

| Level | Color | Token | Usage |
|-------|-------|-------|-------|
| High (70+) | Green | `score-high` | High confidence scores |
| Medium (40-69) | Yellow `#facc15` | `score-medium` | Medium confidence scores |
| Low (<40) | Red | `score-low` | Low confidence scores |

#### Environment Badges
Use for environment indicators:

| Environment | Color | Token | Muted Variant | Usage |
|-------------|-------|-------|---------------|-------|
| Development | Amber `#fbbf24` | `env-dev` | `env-dev-muted` | DEV badge |
| Production | Red `#f87171` | `env-prod` | `env-prod-muted` | PROD badge (warning) |

```tsx
// P&L context
<span className="text-accent-bullish">+$1,234.56</span>
<span className="text-accent-bearish">-$567.89</span>

// Screener context
<Badge className="bg-signal-long-muted text-signal-long border-signal-long">LONG</Badge>
<Badge className="bg-signal-short-muted text-signal-short border-signal-short">SHORT</Badge>

// Technical indicator context
<TrendingUp className="text-up-indicator" />
<TrendingDown className="text-down-indicator" />

// Score context
<span className="text-score-high">85</span>
<span className="text-score-medium">52</span>
<span className="text-score-low">23</span>

// Environment badge
<span className="bg-env-prod-muted text-env-prod">PROD</span>
```

### Glow Effects

Use sparingly for emphasis on key data:

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| **Bullish Glow** | `rgba(0,210,106,0.4)` | `--glow-bullish` | Hero section positive state |
| **Bearish Glow** | `rgba(255,71,87,0.4)` | `--glow-bearish` | Hero section negative state |
| **Primary Glow** | `rgba(99,102,241,0.3)` | `--glow-primary` | Focus states |

### Chart Colors

| Element | Color | Usage |
|---------|-------|-------|
| Bullish Candle | `#10b981` | Up candles |
| Bearish Candle | `#ef4444` | Down candles |
| Wick | `#6b7280` | Candle wicks |
| MA 20 | `#3b82f6` | Moving average line |
| Volume Up | `#10b981` | Up volume bars |
| Volume Down | `#ef4444` | Down volume bars |
| CCI Line | `#a855f7` | CCI indicator |
| CCI Reference | `#4b5563` | CCI ±100 lines |

### WCAG Compliance

All text colors meet WCAG 2.1 Level AA requirements (4.5:1 minimum contrast ratio).

| Color | Contrast | Status |
|-------|----------|--------|
| `--text-primary` (#f8fafc) | 15.8:1 | ✅ AAA |
| `--text-secondary` (#94a3b8) | 7.2:1 | ✅ AA |
| `--text-muted` (#64748b) | 4.6:1 | ✅ AA |
| `--accent-bullish` (#00d26a) | 8.4:1 | ✅ AAA |
| `--accent-bearish` (#ff4757) | 5.2:1 | ✅ AA |
| `--accent-primary` (#6366f1) | 4.8:1 | ✅ AA |

### Forbidden Patterns

```tsx
// ❌ Never use hardcoded Tailwind colors for semantic meaning
<span className="text-green-500">...</span>
<span className="text-red-500">...</span>
<span className="text-green-600">...</span>
<span className="text-red-600">...</span>

// ❌ Never use inline color styles
<span style={{ color: '#ff0000' }}>...</span>

// ❌ Never use dark: prefix (broken in Tailwind v4)
<span className="text-black dark:text-white">...</span>

// ✅ Always use semantic tokens
<span className="text-accent-bullish">...</span>      // P&L profits
<span className="text-accent-bearish">...</span>      // P&L losses
<span className="text-signal-long">...</span>         // Long signals
<span className="text-signal-short">...</span>        // Short signals
<span className="text-up-indicator">...</span>        // Upward indicators
<span className="text-down-indicator">...</span>      // Downward indicators
<span className="text-score-medium">...</span>        // Medium scores
```

---

## Background Patterns

### Grid Pattern

Apply a subtle grid overlay to create depth on page backgrounds:

```css
.page-bg {
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(99, 102, 241, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99, 102, 241, 0.02) 1px, transparent 1px);
  background-size: 60px 60px;
  pointer-events: none;
  z-index: 0;
}
```

### Radial Glow

Use radial gradients for emphasis on hero sections:

```css
.hero-glow {
  position: absolute;
  top: -50px;
  right: -50px;
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, var(--glow-bullish) 0%, transparent 70%);
  opacity: 0.25;
  pointer-events: none;
}
```

---

## Elevation System

### Border-Based Elevation (Dark Mode)

In trading terminal dark mode, use **borders and background layers** instead of shadows:

| Level | Background | Border | Usage |
|-------|------------|--------|-------|
| Base | `bg-bg-primary` | none | Page background |
| Surface | `bg-bg-secondary` | `border-subtle` | Sidebars, nav, cards |
| Elevated | `bg-bg-tertiary` | `border-default` | Panels, inputs, dropdowns |
| Focus | `bg-bg-elevated` | `border-primary` | Hover states, active items |

```tsx
// Sidebar
<aside className="bg-bg-secondary border-r border-subtle">

// Card
<div className="bg-bg-secondary border border-default rounded-lg">

// Active list item
<div className="bg-accent-primary-muted border border-accent-primary rounded-lg">

// Input field
<input className="bg-bg-tertiary border border-default focus:border-accent-primary">
```

### Shadow Usage (Modals Only)

Reserve shadows for floating elements that need clear separation:

```css
--elevation-modal: 0 8px 32px rgba(0, 0, 0, 0.5);
```

---

## Spacing Scale

Use Tailwind's default 4px-based spacing system consistently:

- `gap-1` (4px): Tight spacing within compact elements
- `gap-2` (8px): Spacing within components
- `gap-3` (12px): Related element spacing
- `gap-4` (16px): Standard spacing between elements
- `gap-6` (24px): Section spacing
- `gap-8` (32px): Major section spacing

### Container Padding

```tsx
// Standard page padding
<div className="px-4 sm:px-6 lg:px-8 py-6">

// Sidebar padding
<div className="p-4">

// Card padding
<div className="p-6">
```

---

## Breakpoints

Use Tailwind's default breakpoints (mobile-first):

| Breakpoint | Min Width | Device Type | Usage |
|------------|-----------|-------------|-------|
| (default) | 320px | Mobile | Base styles |
| `sm` | 640px | Mobile landscape | Minor adjustments |
| `md` | 768px | Tablet | Navigation switch, layout changes |
| `lg` | 1024px | Desktop | Secondary sidebars, wide layouts |
| `xl` | 1280px | Large desktop | Maximum content width |

---

## Motion & Animation

### Principles

- CSS-only animations for performance
- Essential micro-interactions only
- Respect `prefers-reduced-motion`
- Fast and subtle (50-200ms)

### Standard Transitions

```css
/* Default transition */
transition: all 0.2s ease;

/* Fast interaction (buttons, toggles) */
transition: all 0.15s ease;

/* Slow emphasis (page loads, reveals) */
transition: all 0.3s ease-out;
```

### Trading-Specific Animations

#### LED Pulse (Connection Status)
```css
@keyframes led-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.status-led {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-bullish);
  box-shadow: 0 0 8px var(--accent-bullish);
  animation: led-pulse 2s ease-in-out infinite;
}
```

#### Badge Dot (Live Indicator)
```css
@keyframes badge-dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

.badge-dot {
  animation: badge-dot-pulse 2s ease-in-out infinite;
}
```

#### Button Press
```css
.button-base:active {
  transform: scale(0.98);
  transition: transform 50ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

#### Card/Item Hover (Desktop Only)
```css
@media (hover: hover) {
  .card-interactive:hover {
    background: var(--bg-tertiary);
    transition: background 150ms ease;
  }
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Responsive Patterns

### Mobile-First Philosophy

Always design for mobile first (320px+), then progressively enhance:

```tsx
// Correct: Mobile-first
<div className="w-full md:w-1/2 lg:w-1/3">

// Wrong: Desktop-first
<div className="w-1/3 lg:w-1/2 md:w-full">
```

### Navigation Patterns

**Mobile (< 768px):**
- Bottom tabs navigation
- Fixed positioning with safe area insets
- 3-4 primary destinations + "More" menu
- Active state clearly visible

**Desktop (>= 768px):**
- Left sidebar navigation (240px width)
- Logo + app title in header
- Environment badge (DEV/PROD)
- Full labels with icons
- Active state: `bg-accent-primary-muted` + `text-accent-primary`

### Layout Patterns

**Two-Panel Layout (Desktop):**
```
+------------------+--------------------------------+
| Nav Sidebar      | Status Bar                     |
| (240px fixed)    +----------------+---------------+
|                  | Watchlist      | Main Content  |
|                  | (260px)        |               |
|                  |                |               |
+------------------+----------------+---------------+
```

**Single Panel (Mobile/Tablet):**
```
+--------------------------------+
| Status Bar                     |
+--------------------------------+
| Main Content                   |
|                                |
+--------------------------------+
| Bottom Tabs                    |
+--------------------------------+
```

### Touch Targets

**CRITICAL**: Minimum touch target size is **44px x 44px** for all interactive elements:

```tsx
// Good - meets minimum
<Button size="lg" className="min-h-[44px] min-w-[44px]">

// Bad - too small for mobile
<Button size="sm" className="h-6 w-6">
```

---

## Component Specifications

### System Status Bar

Top bar showing broker connection and account info.

**Structure:**
```
[LED] Broker Connected | [PAPER] | Account: xxx | Balance: $xxx | Unrealized: +$xxx | Realized: +$xxx
```

**Responsive:**
- Desktop: Full display with all fields
- Mobile: LED + Badge + Balance only (hide P&L)

**Styling:**
```tsx
<header className="bg-bg-secondary border-b border-subtle px-6 py-3 flex items-center gap-6">
  <div className="flex items-center gap-2">
    <span className="status-led" />
    <span className="text-text-muted text-sm">Broker</span>
    <span className="font-mono text-sm">Connected</span>
  </div>
  <span className="status-badge-paper">PAPER</span>
  {/* ... more items */}
</header>
```

### Hero Price Display

Large-format price display for primary stock info.

**Structure:**
```
AAPL [Bullish Badge]
$198.45  +$4.52 (+2.34% today)
```

**Typography:**
- Symbol: `text-4xl font-display font-bold`
- Price: `text-5xl font-mono font-bold`
- Change: `text-lg font-mono font-semibold` + color

**Effects:**
- Radial glow matching bullish/bearish state
- Pulse dot on status badge

```tsx
<div className="stock-hero relative overflow-hidden">
  <div className="hero-glow-bullish" /> {/* Radial glow */}
  <div className="relative z-10">
    <div className="flex items-center gap-4">
      <span className="text-4xl font-display font-bold">AAPL</span>
      <span className="badge-bullish">
        <span className="badge-dot" />
        Bullish
      </span>
    </div>
    <div className="flex items-baseline gap-4 mt-2">
      <span className="text-5xl font-mono font-bold">$198.45</span>
      <div>
        <span className="text-lg font-mono text-accent-bullish">+$4.52</span>
        <span className="text-sm text-text-muted ml-2">+2.34% today</span>
      </div>
    </div>
  </div>
</div>
```

### Watchlist Item with Sparkline

Quick-switch symbol list with trend context.

**Structure:**
```
[Symbol]  [Sparkline]  [Change%]
[Price]
```

**Elements:**
- Symbol: `font-mono font-bold text-sm`
- Price: `font-mono text-xs text-text-secondary`
- Sparkline: 40x20px SVG polyline
- Change: `font-mono text-xs` + bullish/bearish color

**States:**
- Default: `bg-transparent`
- Hover: `bg-bg-tertiary`
- Active: `bg-accent-primary-muted border border-accent-primary`

```tsx
<div className={cn(
  "flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors",
  isActive
    ? "bg-accent-primary-muted border border-accent-primary"
    : "hover:bg-bg-tertiary"
)}>
  <div className="flex-1">
    <div className="font-mono font-bold text-sm">{symbol}</div>
    <div className="font-mono text-xs text-text-secondary">{price}</div>
  </div>
  <svg className="w-10 h-5" viewBox="0 0 40 20">
    <polyline
      className={isBullish ? "stroke-accent-bullish" : "stroke-accent-bearish"}
      fill="none"
      strokeWidth="1.5"
      points={sparklinePoints}
    />
  </svg>
  <span className={cn(
    "font-mono text-xs font-semibold",
    isBullish ? "text-accent-bullish" : "text-accent-bearish"
  )}>
    {changePercent}
  </span>
</div>
```

### Indicator Toggle Buttons

Chart indicator controls with color-coded active states.

**Structure:**
```
[Icon] MA 20  |  [Icon] Vol  |  [Icon] CCI
```

**States:**
- Inactive: `bg-bg-secondary border-default text-text-secondary`
- Active: `border-[indicator-color] text-[indicator-color] bg-[indicator-color]/10`

**Colors by Indicator:**
- MA 20: `#3b82f6` (blue)
- Volume: `#10b981` (green)
- CCI: `#a855f7` (purple)

```tsx
<button className={cn(
  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-semibold",
  "border transition-colors",
  isActive
    ? "border-blue-500 text-blue-500 bg-blue-500/10"
    : "border-default text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
)}>
  <span className="w-2.5 h-2.5 rounded-sm bg-current" />
  MA 20
</button>
```

---

## Component Usage

### Button Components

Use shadcn/ui Button exclusively. Do not create custom button implementations.

```tsx
import { Button } from '@/components/ui/button';

// Variants
<Button variant="default">Primary Action</Button>
<Button variant="secondary">Secondary Action</Button>
<Button variant="destructive">Delete</Button>
<Button variant="outline">Cancel</Button>
<Button variant="ghost">Subtle Action</Button>

// Sizes
<Button size="default">Default</Button>
<Button size="sm">Small</Button>
<Button size="lg">Large</Button>
<Button size="icon">Icon Only</Button>
```

### Card Components

```tsx
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';

<Card className="bg-bg-secondary border-default">
  <CardHeader>
    <CardTitle className="font-display">Title</CardTitle>
  </CardHeader>
  <CardContent>
    Content here
  </CardContent>
</Card>
```

### Badge Components

```tsx
import { Badge } from '@/components/ui/badge';

// Standard variants
<Badge variant="default">Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Error</Badge>
<Badge variant="outline">Outline</Badge>

// Trading badges
<Badge className="bg-accent-bullish text-white">Bullish</Badge>
<Badge className="bg-accent-bearish text-white">Bearish</Badge>
<Badge className="bg-amber-500/15 text-amber-500 border border-amber-500/30">PAPER</Badge>
```

### Input Components

```tsx
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

<div>
  <Label htmlFor="ticker" className="text-sm text-text-muted">Ticker Symbol</Label>
  <Input
    id="ticker"
    type="text"
    placeholder="AAPL"
    className="font-mono uppercase bg-bg-tertiary border-default focus:border-accent-primary"
  />
</div>
```

---

## Implementation Patterns

### Using Semantic Colors

```tsx
import { POSITION_COLORS } from '@/constants/colors';

// Dynamic color based on value
<span className={POSITION_COLORS.profitLoss(pnlValue)}>
  ${pnlValue}
</span>
```

### Responsive Component Switching

```tsx
import { useResponsive } from '@/hooks/useResponsive';

const { isMobile, isTablet, isDesktop, mounted } = useResponsive();

// Prevent hydration mismatch
if (!mounted) return null;

return isMobile ? <MobileView /> : <DesktopView />;
```

### Responsive Layouts

```tsx
// Mobile-first grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  {items.map(item => <Card key={item.id}>{item.content}</Card>)}
</div>

// Two-panel layout (desktop)
<div className="grid grid-cols-1 lg:grid-cols-[260px_1fr]">
  <aside className="hidden lg:block">Sidebar</aside>
  <main>Content</main>
</div>
```

---

## Development Checklist

Before submitting any UI changes:

- [ ] Typography uses correct font family (display/body/data)
- [ ] All numeric displays use `font-mono` class
- [ ] Colors use semantic tokens (no hardcoded hex values)
- [ ] Background uses layered system (`bg-bg-primary`, `bg-bg-secondary`, etc.)
- [ ] Borders use `border-subtle` or `border-default`
- [ ] Mobile-first responsive patterns applied
- [ ] Touch targets meet 44px minimum on mobile
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Component uses shadcn/ui primitives (no custom duplicates)
- [ ] Tested at 375px (mobile), 768px (tablet), 1920px (desktop)
- [ ] No horizontal scroll (except intentional)
- [ ] TypeScript compiles with 0 errors

---

## Resources

- [shadcn/ui Documentation](https://ui.shadcn.com/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Mobile-First Design](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Responsive/Mobile_first)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- Implementation: `frontend/src/index.css` (CSS variables and @theme block)
