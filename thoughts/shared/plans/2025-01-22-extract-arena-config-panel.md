# Extract ArenaConfigPanel Component - Implementation Plan

## Task Classification

**Task Type**: Frontend-heavy

## Required Agent Consultations

| Agent | Consulted | Key Recommendations Incorporated |
|-------|-----------|----------------------------------|
| frontend-engineer | ✅ Yes | Extract only Configuration Panel; pass full Simulation object; internal expand state; flat file structure |
| backend-engineer | ⬜ N/A | No backend changes required |

## Overview

Extract the Configuration Panel section (~115 lines) from `ArenaSimulationDetail.tsx` into a dedicated `ArenaConfigPanel.tsx` component. This improves code organization and creates a reusable component for displaying simulation configuration.

## Current State Analysis

**File**: `frontend/src/pages/ArenaSimulationDetail.tsx` (429 lines)

The page has three main inline sections:
1. Header (lines 175-237, 62 lines) - navigation, title, action buttons
2. **Configuration Panel (lines 240-355, 115 lines)** - target for extraction
3. Progress Card (lines 358-391, 33 lines) - progress bar and status

### Key Discoveries:
- Configuration Panel is self-contained with only `simulation` data dependency
- Expand/collapse state for symbols is internal presentation logic
- Existing arena components follow pattern: JSDoc, props interface, `simulation: Simulation` prop
- Helper `formatTrailingStop` already exists in `utils/arena.ts`

## Desired End State

- `ArenaSimulationDetail.tsx` reduced to ~315 lines (from 429)
- New `ArenaConfigPanel.tsx` component (~120 lines) in `components/arena/`
- New `ArenaConfigPanel.test.tsx` with comprehensive test coverage
- Zero behavior changes - pure refactoring
- All tests pass, TypeScript compiles cleanly

## What We're NOT Doing

- NOT extracting Header section (page-specific with navigation/callbacks)
- NOT extracting Progress Card (too small, 33 lines)
- NOT changing any behavior or styling
- NOT creating a subfolder (only one component being extracted)
- NOT modifying the Simulation type or API

## Implementation Approach

Single-phase pure refactoring: create component, create tests, update page, verify.

---

## Phase 1: Create ArenaConfigPanel Component

### Overview
Create the new component with props interface, JSDoc, and internal expand/collapse state.

### Changes Required:

#### 1. Create `frontend/src/components/arena/ArenaConfigPanel.tsx`

**File**: `frontend/src/components/arena/ArenaConfigPanel.tsx`
**Changes**: New file

```typescript
/**
 * Arena Configuration Panel
 *
 * Displays simulation parameters including date range, agent type,
 * trailing stop, min score, and expandable symbols list.
 */
import { useState } from 'react';
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  Settings2,
  Target,
  TrendingDown,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { formatTrailingStop } from '../../utils/arena';
import type { Simulation } from '../../types/arena';

/** Default number of symbols shown before expansion */
const SYMBOLS_PREVIEW_COUNT = 8;

interface ArenaConfigPanelProps {
  /** Simulation configuration to display */
  simulation: Simulation;
}

/**
 * Arena Configuration Panel Component
 *
 * Shows simulation parameters in a grid layout:
 * - Date range (start → end)
 * - Agent type
 * - Trailing stop percentage
 * - Minimum buy score
 * - Expandable symbols list
 */
export const ArenaConfigPanel = ({ simulation }: ArenaConfigPanelProps) => {
  const [symbolsExpanded, setSymbolsExpanded] = useState(false);

  const hasMoreSymbols = simulation.symbols.length > SYMBOLS_PREVIEW_COUNT;
  const displayedSymbols = symbolsExpanded
    ? simulation.symbols
    : simulation.symbols.slice(0, SYMBOLS_PREVIEW_COUNT);

  return (
    <Card className="bg-bg-secondary border-border-subtle">
      <CardContent className="pt-5 pb-4">
        {/* Configuration Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          {/* Date Range */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-text-muted">
              <Calendar className="h-3.5 w-3.5" />
              <span className="text-[11px] font-medium uppercase tracking-wider">
                Date Range
              </span>
            </div>
            <p className="font-mono text-sm text-text-primary">
              {simulation.start_date} → {simulation.end_date}
            </p>
          </div>

          {/* Agent Type */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-text-muted">
              <Settings2 className="h-3.5 w-3.5" />
              <span className="text-[11px] font-medium uppercase tracking-wider">
                Agent
              </span>
            </div>
            <p className="font-mono text-sm text-text-primary">
              {simulation.agent_type}
            </p>
          </div>

          {/* Trailing Stop */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-text-muted">
              <TrendingDown className="h-3.5 w-3.5" />
              <span className="text-[11px] font-medium uppercase tracking-wider">
                Trailing Stop
              </span>
            </div>
            <p className="font-mono text-sm">
              <span
                className={
                  simulation.trailing_stop_pct != null
                    ? 'text-accent-bearish'
                    : 'text-text-muted'
                }
              >
                {formatTrailingStop(simulation.trailing_stop_pct)}
              </span>
            </p>
          </div>

          {/* Min Buy Score */}
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-text-muted">
              <Target className="h-3.5 w-3.5" />
              <span className="text-[11px] font-medium uppercase tracking-wider">
                Min Score
              </span>
            </div>
            <p className="font-mono text-sm">
              {simulation.min_buy_score != null ? (
                <span className="text-accent-primary">
                  {simulation.min_buy_score}
                </span>
              ) : (
                <span className="text-text-muted">—</span>
              )}
            </p>
          </div>
        </div>

        {/* Symbols Section */}
        <div className="pt-3 border-t border-border-subtle">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
              Symbols ({simulation.symbols.length})
            </span>
            {hasMoreSymbols && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSymbolsExpanded(!symbolsExpanded)}
                className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                {symbolsExpanded ? (
                  <>
                    <ChevronUp className="h-3 w-3 mr-1" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3 mr-1" />
                    Show all {simulation.symbols.length}
                  </>
                )}
              </Button>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {displayedSymbols.map((symbol) => (
              <span
                key={symbol}
                className="px-2 py-0.5 text-xs font-mono bg-bg-tertiary text-text-secondary rounded border border-border-subtle"
              >
                {symbol}
              </span>
            ))}
            {!symbolsExpanded && hasMoreSymbols && (
              <span className="px-2 py-0.5 text-xs font-mono text-text-muted">
                +{simulation.symbols.length - SYMBOLS_PREVIEW_COUNT} more
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

#### 2. Create `frontend/src/components/arena/ArenaConfigPanel.test.tsx`

**File**: `frontend/src/components/arena/ArenaConfigPanel.test.tsx`
**Changes**: New test file

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ArenaConfigPanel } from './ArenaConfigPanel';
import type { Simulation } from '../../types/arena';

const createMockSimulation = (overrides: Partial<Simulation> = {}): Simulation => ({
  id: 1,
  name: 'Test Simulation',
  stock_list_id: null,
  stock_list_name: null,
  symbols: ['AAPL', 'GOOGL', 'MSFT'],
  start_date: '2024-01-01',
  end_date: '2024-03-01',
  initial_capital: '10000',
  position_size: '1000',
  agent_type: 'live20',
  trailing_stop_pct: '5.0',
  min_buy_score: 60,
  status: 'completed',
  current_day: 40,
  total_days: 40,
  final_equity: '11500',
  total_return_pct: '15.0',
  total_trades: 10,
  winning_trades: 7,
  max_drawdown_pct: '3.5',
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

describe('ArenaConfigPanel', () => {
  it('renders date range', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('2024-01-01 → 2024-03-01')).toBeInTheDocument();
  });

  it('renders agent type', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('live20')).toBeInTheDocument();
  });

  it('renders trailing stop percentage', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('-5.0%')).toBeInTheDocument();
  });

  it('renders dash for null trailing stop', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation({ trailing_stop_pct: null })} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('renders min buy score', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('60')).toBeInTheDocument();
  });

  it('renders dash for null min buy score', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation({ min_buy_score: null })} />);
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('renders symbol count', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('Symbols (3)')).toBeInTheDocument();
  });

  it('renders all symbols when count is below threshold', () => {
    render(<ArenaConfigPanel simulation={createMockSimulation()} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('shows expand button when symbols exceed threshold', () => {
    const manySymbols = Array.from({ length: 12 }, (_, i) => `SYM${i}`);
    render(<ArenaConfigPanel simulation={createMockSimulation({ symbols: manySymbols })} />);
    expect(screen.getByText('Show all 12')).toBeInTheDocument();
    expect(screen.getByText('+4 more')).toBeInTheDocument();
  });

  it('expands and collapses symbols list', async () => {
    const user = userEvent.setup();
    const manySymbols = Array.from({ length: 12 }, (_, i) => `SYM${i}`);
    render(<ArenaConfigPanel simulation={createMockSimulation({ symbols: manySymbols })} />);

    // Initially collapsed - SYM11 should not be visible
    expect(screen.queryByText('SYM11')).not.toBeInTheDocument();

    // Expand
    await user.click(screen.getByText('Show all 12'));
    expect(screen.getByText('SYM11')).toBeInTheDocument();
    expect(screen.getByText('Show less')).toBeInTheDocument();

    // Collapse
    await user.click(screen.getByText('Show less'));
    expect(screen.queryByText('SYM11')).not.toBeInTheDocument();
  });
});
```

#### 3. Update `frontend/src/pages/ArenaSimulationDetail.tsx`

**File**: `frontend/src/pages/ArenaSimulationDetail.tsx`
**Changes**: Replace inline configuration panel with component import

**Remove these imports** (no longer needed in detail page):
```typescript
// Remove from imports:
Calendar,
ChevronDown,
ChevronUp,
Settings2,
Target,
TrendingDown,
```

**Add new import:**
```typescript
import { ArenaConfigPanel } from '../components/arena/ArenaConfigPanel';
```

**Remove this import from utils/arena** (no longer used directly):
```typescript
// Remove from utils/arena import:
formatTrailingStop,
```

**Remove state declaration:**
```typescript
// Remove this line:
const [symbolsExpanded, setSymbolsExpanded] = useState(false);
```

**Remove computed values after line 164:**
```typescript
// Remove these lines:
const SYMBOLS_PREVIEW_COUNT = 8;
const hasMoreSymbols = simulation.symbols.length > SYMBOLS_PREVIEW_COUNT;
const displayedSymbols = symbolsExpanded
  ? simulation.symbols
  : simulation.symbols.slice(0, SYMBOLS_PREVIEW_COUNT);
```

**Replace inline JSX (lines 240-355)** with:
```typescript
{/* Configuration Panel */}
<ArenaConfigPanel simulation={simulation} />
```

### Success Criteria:

#### Automated Verification:
- [x] Read testing guide: `docs/guides/testing.md`
- [x] Backend tests pass (100%): See testing guide for command
- [x] Frontend tests pass (100%): 754/754 tests pass
- [x] TypeScript 0 errors: tsc -b --noEmit passes

#### Manual Verification:
- [ ] Navigate to Arena simulation detail page
- [ ] Verify all 4 config fields display correctly (date range, agent, trailing stop, min score)
- [ ] Verify symbols list shows first 8 symbols
- [ ] Click "Show all X" and verify all symbols appear
- [ ] Click "Show less" and verify collapse works
- [ ] Verify styling matches exactly (no visual changes)

**Implementation Note**: This is a single-phase pure refactoring. All changes should be made together and verified as a unit.

---

## Testing Strategy

### Unit Tests:
- `ArenaConfigPanel.test.tsx` covers:
  - Rendering all configuration fields
  - Null/undefined handling for optional fields
  - Symbol count display
  - Expand/collapse interaction

### Integration Tests:
- Existing detail page tests continue to pass (if any)
- No new integration tests needed for pure refactoring

### Manual Testing Steps:
1. Start frontend dev server
2. Navigate to `/arena`
3. Click on any completed simulation
4. Verify config panel renders identically to before
5. Test symbol expand/collapse
6. Test with simulation that has null trailing_stop_pct
7. Test with simulation that has null min_buy_score

## References

- Original P4 item from engineering standards review
- Existing pattern: `frontend/src/components/arena/ArenaResultsTable.tsx`
- Types: `frontend/src/types/arena.ts`
- Utility: `frontend/src/utils/arena.ts` (formatTrailingStop)
