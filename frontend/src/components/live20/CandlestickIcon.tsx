/**
 * SVG Candlestick Icons for Live 20
 *
 * Visual representations of candlestick patterns showing the actual shape
 * (body, upper wick, lower wick). Color is determined by actual price movement
 * (green if close > open, red if close < open).
 */

interface CandlestickIconProps {
  /** The candlestick pattern to display (determines shape) */
  pattern: string | null;
  /** Whether the candle is bullish (close > open) - determines color */
  bullish?: boolean | null;
  /** Size of the icon in pixels */
  size?: number;
  /** Optional additional CSS classes */
  className?: string;
}

// Colors
const GREEN = '#22c55e'; // Tailwind green-500
const RED = '#ef4444'; // Tailwind red-500
const GRAY = '#6b7280'; // Tailwind gray-500

/**
 * Get color based on bullish/bearish status
 */
function getColor(bullish: boolean | null | undefined): string {
  if (bullish === null || bullish === undefined) return GRAY;
  return bullish ? GREEN : RED;
}

/**
 * Pattern shape definitions
 * Each pattern has: bodyTop, bodyHeight, upperWick, lowerWick (all 0-100 scale)
 */
const patternShapes: Record<string, { bodyTop: number; bodyHeight: number; upperWick: number; lowerWick: number }> = {
  doji: { bodyTop: 45, bodyHeight: 10, upperWick: 35, lowerWick: 35 },
  hammer: { bodyTop: 15, bodyHeight: 20, upperWick: 5, lowerWick: 55 },
  hanging_man: { bodyTop: 15, bodyHeight: 20, upperWick: 5, lowerWick: 55 },  // Same shape as hammer
  shooting_star: { bodyTop: 60, bodyHeight: 20, upperWick: 50, lowerWick: 5 },
  inverted_hammer: { bodyTop: 60, bodyHeight: 20, upperWick: 50, lowerWick: 5 },  // Same shape as shooting star
  engulfing_bullish: { bodyTop: 15, bodyHeight: 70, upperWick: 5, lowerWick: 5 },
  engulfing_bearish: { bodyTop: 15, bodyHeight: 70, upperWick: 5, lowerWick: 5 },
  marubozu_bullish: { bodyTop: 10, bodyHeight: 80, upperWick: 0, lowerWick: 0 },
  marubozu_bearish: { bodyTop: 10, bodyHeight: 80, upperWick: 0, lowerWick: 0 },
  spinning_top: { bodyTop: 40, bodyHeight: 20, upperWick: 30, lowerWick: 30 },
  standard: { bodyTop: 25, bodyHeight: 50, upperWick: 15, lowerWick: 15 },
};

/**
 * SVG Candlestick component
 * Renders a candlestick with configurable body position, wick lengths, and color
 */
function Candlestick({
  bodyTop,
  bodyHeight,
  upperWick,
  lowerWick,
  color,
  size = 24,
}: {
  bodyTop: number; // 0-100, where body starts from top
  bodyHeight: number; // 0-100, body height
  upperWick: number; // 0-100, wick above body
  lowerWick: number; // 0-100, wick below body
  color: string;
  size?: number;
}) {
  const width = size;
  const height = size;
  const bodyWidth = width * 0.5;
  const wickWidth = 2;

  // Convert percentages to actual pixel values
  const scale = height / 100;
  const bodyY = bodyTop * scale;
  const bodyH = Math.max(bodyHeight * scale, 2); // Min 2px body
  const upperWickH = upperWick * scale;
  const lowerWickH = lowerWick * scale;

  const centerX = width / 2;
  const bodyX = centerX - bodyWidth / 2;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {/* Upper wick */}
      {upperWickH > 0 && (
        <line
          x1={centerX}
          y1={bodyY - upperWickH}
          x2={centerX}
          y2={bodyY}
          stroke={color}
          strokeWidth={wickWidth}
          strokeLinecap="round"
        />
      )}
      {/* Body */}
      <rect
        x={bodyX}
        y={bodyY}
        width={bodyWidth}
        height={bodyH}
        fill={color}
        rx={1}
      />
      {/* Lower wick */}
      {lowerWickH > 0 && (
        <line
          x1={centerX}
          y1={bodyY + bodyH}
          x2={centerX}
          y2={bodyY + bodyH + lowerWickH}
          stroke={color}
          strokeWidth={wickWidth}
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

/**
 * Main CandlestickIcon component
 *
 * Renders a candlestick icon where:
 * - Shape is determined by the pattern (hammer, doji, etc.)
 * - Color is determined by bullish prop (green if close > open, red if close < open)
 */
export function CandlestickIcon({ pattern, bullish, size = 24, className = '' }: CandlestickIconProps) {
  const patternKey = pattern?.toLowerCase() || 'standard';
  const shape = patternShapes[patternKey] || patternShapes.standard;
  const color = getColor(bullish);

  return (
    <span className={`inline-flex items-center justify-center ${className}`}>
      <Candlestick
        bodyTop={shape.bodyTop}
        bodyHeight={shape.bodyHeight}
        upperWick={shape.upperWick}
        lowerWick={shape.lowerWick}
        color={color}
        size={size}
      />
    </span>
  );
}
