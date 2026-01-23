import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

expect.extend(matchers);

afterEach(() => {
  cleanup();
});

// Mock lightweight-charts library
vi.mock('lightweight-charts', () => {
  const mockSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
    createPriceLine: vi.fn(),
  };

  const mockMarkersPlugin = {
    setMarkers: vi.fn(),
    markers: vi.fn().mockReturnValue([]),
  };

  const mockTimeScale = {
    subscribeVisibleLogicalRangeChange: vi.fn(),
    setVisibleRange: vi.fn(),
    fitContent: vi.fn(),
    coordinateToTime: vi.fn(),
  };

  const mockPriceScale = {
    applyOptions: vi.fn(),
  };

  const mockPane = {
    setHeight: vi.fn(),
  };

  const mockChart = {
    addSeries: vi.fn().mockReturnValue(mockSeries),
    removeSeries: vi.fn(),
    remove: vi.fn(),
    applyOptions: vi.fn(),
    timeScale: vi.fn().mockReturnValue(mockTimeScale),
    priceScale: vi.fn().mockReturnValue(mockPriceScale),
    panes: vi.fn().mockReturnValue([mockPane, mockPane, mockPane]),
  };

  return {
    createChart: vi.fn().mockReturnValue(mockChart),
    createSeriesMarkers: vi.fn().mockReturnValue(mockMarkersPlugin),
    CandlestickSeries: 'CandlestickSeries',
    LineSeries: 'LineSeries',
    HistogramSeries: 'HistogramSeries',
    ColorType: {
      Solid: 'solid',
    },
  };
});

// Mock window.matchMedia for Lightweight Charts
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // Deprecated
    removeListener: vi.fn(), // Deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock ResizeObserver for responsive charts
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock localStorage for hooks that persist state (e.g., useChartZoom)
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock pointer events for Radix UI components (Select, etc.)
// JSDOM doesn't implement hasPointerCapture, which Radix requires
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => undefined;
Element.prototype.releasePointerCapture = () => undefined;

// Mock scrollIntoView for Radix UI Select component
Element.prototype.scrollIntoView = vi.fn();

// Mock HTMLCanvasElement.getContext for chart rendering
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  fillRect: vi.fn(),
  clearRect: vi.fn(),
  getImageData: vi.fn(),
  putImageData: vi.fn(),
  createImageData: vi.fn(),
  setTransform: vi.fn(),
  drawImage: vi.fn(),
  save: vi.fn(),
  fillText: vi.fn(),
  restore: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  closePath: vi.fn(),
  stroke: vi.fn(),
  translate: vi.fn(),
  scale: vi.fn(),
  rotate: vi.fn(),
  arc: vi.fn(),
  fill: vi.fn(),
  measureText: vi.fn().mockReturnValue({ width: 0 }),
  transform: vi.fn(),
  rect: vi.fn(),
  clip: vi.fn(),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}) as any;
