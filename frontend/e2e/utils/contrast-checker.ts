/**
 * Contrast Checker Utility
 *
 * Provides functions to calculate WCAG 2.1 contrast ratios and verify text visibility.
 * Used in E2E tests to programmatically verify UI text contrast meets accessibility standards.
 *
 * @see https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
 */

/**
 * Parse RGB color string to array of numbers
 * @param rgb - Color string in format "rgb(r, g, b)" or "rgba(r, g, b, a)"
 * @returns Array of [r, g, b] values (0-255)
 */
export function parseRgbColor(rgb: string): [number, number, number] {
  const match = rgb.match(/\d+/g);
  if (!match || match.length < 3) {
    throw new Error(`Invalid RGB color format: ${rgb}`);
  }
  return [parseInt(match[0]), parseInt(match[1]), parseInt(match[2])];
}

/**
 * Calculate relative luminance of a color according to WCAG 2.1
 * @param rgb - Array of [r, g, b] values (0-255)
 * @returns Relative luminance (0-1)
 */
export function calculateLuminance(rgb: [number, number, number]): number {
  const [r, g, b] = rgb.map(channel => {
    const normalized = channel / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : Math.pow((normalized + 0.055) / 1.055, 2.4);
  });

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculate WCAG 2.1 contrast ratio between two colors
 * @param color1 - RGB color string for foreground (e.g., "rgb(17, 24, 39)")
 * @param color2 - RGB color string for background (e.g., "rgb(255, 255, 255)")
 * @returns Contrast ratio (1-21)
 */
export function calculateContrastRatio(color1: string, color2: string): number {
  const rgb1 = parseRgbColor(color1);
  const rgb2 = parseRgbColor(color2);

  const lum1 = calculateLuminance(rgb1);
  const lum2 = calculateLuminance(rgb2);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Check if contrast ratio meets WCAG standards
 * @param ratio - Contrast ratio (1-21)
 * @param level - WCAG level to check ('AA' | 'AAA')
 * @param isLargeText - Whether text is considered large (18pt+ or 14pt+ bold)
 * @returns Object with pass/fail status and threshold
 */
export function checkWCAGCompliance(
  ratio: number,
  level: 'AA' | 'AAA' = 'AA',
  isLargeText: boolean = false
): { passes: boolean; threshold: number; level: string } {
  let threshold: number;

  if (level === 'AAA') {
    threshold = isLargeText ? 4.5 : 7;
  } else {
    // AA
    threshold = isLargeText ? 3 : 4.5;
  }

  return {
    passes: ratio >= threshold,
    threshold,
    level: `WCAG ${level}`,
  };
}

/**
 * Style analysis result from element
 */
export interface StyleAnalysis {
  color: string;
  backgroundColor: string;
  opacity: string;
  display: string;
  visibility: string;
  fontSize: string;
  fontWeight: string;
}

/**
 * Contrast analysis result
 */
export interface ContrastAnalysis {
  foreground: string;
  background: string;
  contrastRatio: number;
  wcagAA: { passes: boolean; threshold: number };
  wcagAAA: { passes: boolean; threshold: number };
  isVisible: boolean;
  opacity: number;
  display: string;
}

/**
 * Analyze contrast and visibility of an element
 * This function is meant to be executed in the browser context via page.evaluate()
 *
 * @param element - DOM element to analyze
 * @returns ContrastAnalysis object
 */
export function analyzeElementContrast(element: Element): ContrastAnalysis {
  const style = window.getComputedStyle(element);

  const foreground = style.color;
  const backgroundColor = style.backgroundColor;
  const opacity = parseFloat(style.opacity);
  const display = style.display;
  const visibility = style.visibility;

  // Helper function to parse RGB
  function rgbToArray(rgb: string): [number, number, number] {
    const match = rgb.match(/\d+/g);
    if (!match || match.length < 3) {
      return [0, 0, 0];
    }
    return [parseInt(match[0]), parseInt(match[1]), parseInt(match[2])];
  }

  // Helper function to calculate luminance
  function luminance(rgb: [number, number, number]): number {
    const [r, g, b] = rgb.map(channel => {
      const normalized = channel / 255;
      return normalized <= 0.03928
        ? normalized / 12.92
        : Math.pow((normalized + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  // Calculate contrast ratio
  const fgRgb = rgbToArray(foreground);
  const bgRgb = rgbToArray(backgroundColor);
  const L1 = luminance(fgRgb);
  const L2 = luminance(bgRgb);
  const contrastRatio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);

  return {
    foreground,
    background: backgroundColor,
    contrastRatio,
    wcagAA: {
      passes: contrastRatio >= 4.5,
      threshold: 4.5,
    },
    wcagAAA: {
      passes: contrastRatio >= 7,
      threshold: 7,
    },
    isVisible: display !== 'none' && visibility !== 'hidden' && opacity > 0,
    opacity,
    display,
  };
}

/**
 * Format contrast analysis results as human-readable string
 */
export function formatContrastReport(analysis: ContrastAnalysis): string {
  const lines = [
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    `Foreground Color: ${analysis.foreground}`,
    `Background Color: ${analysis.background}`,
    `Contrast Ratio: ${analysis.contrastRatio.toFixed(2)}:1`,
    `WCAG AA (4.5:1): ${analysis.wcagAA.passes ? '✓ PASS' : '✗ FAIL'}`,
    `WCAG AAA (7:1): ${analysis.wcagAAA.passes ? '✓ PASS' : '✗ FAIL'}`,
    `Visibility: ${analysis.isVisible ? '✓ Visible' : '✗ Hidden'} (opacity: ${analysis.opacity}, display: ${analysis.display})`,
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
  ];
  return lines.join('\n');
}
