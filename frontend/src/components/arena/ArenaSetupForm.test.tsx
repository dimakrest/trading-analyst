import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ArenaSetupForm } from './ArenaSetupForm';

// Mock useStockLists hook
const mockLists = [
  { id: 1, name: 'Tech Stocks', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
  { id: 2, name: 'Energy', symbols: ['XOM', 'CVX'], symbol_count: 2 },
];

vi.mock('../../hooks/useStockLists', () => ({
  useStockLists: vi.fn(() => ({
    lists: mockLists,
    isLoading: false,
    error: null,
    createList: vi.fn(),
    updateList: vi.fn(),
    deleteList: vi.fn(),
    refetch: vi.fn(),
  })),
}));

vi.mock('../../hooks/useAgentConfigs', () => ({
  useAgentConfigs: vi.fn(() => ({
    configs: [],
    selectedConfigId: undefined,
    setSelectedConfigId: vi.fn(),
    isLoading: false,
    error: null,
  })),
}));

describe('ArenaSetupForm', () => {
  const mockOnSubmit = vi.fn();
  const mockOnSubmitComparison = vi.fn();

  beforeEach(() => {
    mockOnSubmit.mockClear();
    mockOnSubmitComparison.mockClear();
  });

  it('should render with empty state', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    expect(screen.getByRole('textbox', { name: /symbols/i })).toBeInTheDocument();
    expect(screen.getByText(/0 symbols/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should show symbol count when symbols are entered', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, NVDA, TSLA' } });

    expect(screen.getByText(/3 symbols/i)).toBeInTheDocument();
  });

  it('should parse symbols separated by comma, space, or newline', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL\nNVDA TSLA,AMD' } });

    expect(screen.getByText(/4 symbols/i)).toBeInTheDocument();
  });

  it('should uppercase symbols automatically', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'aapl, nvda' } });

    expect(screen.getByText(/2 symbols/i)).toBeInTheDocument();
  });

  it('should filter out invalid symbols', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    // Empty strings and very long symbols should be filtered out
    fireEvent.change(textarea, { target: { value: 'AAPL, , VERYLONGSYMBOLNAME, NVDA' } });

    expect(screen.getByText(/2 symbols/i)).toBeInTheDocument();
  });

  it('should have disabled submit button when no dates entered', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, NVDA' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should have disabled submit button when start date is after end date', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);

    fireEvent.change(startDateInput, { target: { value: '2024-01-15' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-01' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should enable submit button with valid inputs', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);

    fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeEnabled();
  });

  it('should call onSubmit with parsed data when form is submitted', async () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    // Fill in form
    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, nvda' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);
    fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

    // Change capital settings
    const capitalInput = screen.getByLabelText(/capital \(\$\)/i);
    fireEvent.change(capitalInput, { target: { value: '50000' } });

    // Submit
    const submitButton = screen.getByRole('button', { name: /start simulation/i });
    fireEvent.click(submitButton);

    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        symbols: ['AAPL', 'NVDA'],
        start_date: '2024-01-01',
        end_date: '2024-01-15',
        initial_capital: 50000,
        position_size: 1000,
        trailing_stop_pct: 5,
        min_buy_score: 60,
        portfolio_strategy: 'none',
        max_per_sector: null,
        max_open_positions: null,
      })
    );
  });

  it('should disable form when loading', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={true} />);

    expect(screen.getByRole('textbox', { name: /symbols/i })).toBeDisabled();
    expect(screen.getByLabelText(/start date/i)).toBeDisabled();
    expect(screen.getByLabelText(/end date/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
  });

  it('should show agent configuration section', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    expect(screen.getByText(/agent configuration/i)).toBeInTheDocument();
    expect(screen.getByText(/live20 mean reversion/i)).toBeInTheDocument();
  });

  it('should have default values for capital settings', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    const capitalInput = screen.getByLabelText(/capital \(\$\)/i) as HTMLInputElement;
    const positionSizeInput = screen.getByLabelText(/position size/i) as HTMLInputElement;
    const trailingStopInput = screen.getByLabelText(/trailing stop/i) as HTMLInputElement;

    expect(capitalInput.value).toBe('10000');
    expect(positionSizeInput.value).toBe('1000');
    expect(trailingStopInput.value).toBe('5');
  });

  describe('Minimum Buy Score', () => {
    it('should have default value of 60', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;
      expect(minBuyScoreInput).toHaveAttribute('id', 'arena-min-buy-score-input');
      expect(minBuyScoreInput.value).toBe('60');
    });

    it('should update when changed', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;
      fireEvent.change(minBuyScoreInput, { target: { value: '80' } });

      expect(minBuyScoreInput.value).toBe('80');
    });

    it('should include min_buy_score in submission', async () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Fill in form
      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      fireEvent.change(textarea, { target: { value: 'AAPL' } });

      const startDateInput = screen.getByLabelText(/start date/i);
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
      fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

      // Change min buy score
      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;
      fireEvent.change(minBuyScoreInput, { target: { value: '80' } });

      // Submit
      const submitButton = screen.getByRole('button', { name: /start simulation/i });
      fireEvent.click(submitButton);

      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          symbols: ['AAPL'],
          start_date: '2024-01-01',
          end_date: '2024-01-15',
          initial_capital: 10000,
          position_size: 1000,
          trailing_stop_pct: 5,
          min_buy_score: 80,
          portfolio_strategy: 'none',
          max_per_sector: null,
          max_open_positions: null,
        })
      );
    });

    it('should disable submit when value is below minimum (5)', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Fill valid data
      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      fireEvent.change(textarea, { target: { value: 'AAPL' } });

      const startDateInput = screen.getByLabelText(/start date/i);
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
      fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

      // Set invalid min buy score (below MIN of 5)
      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;
      fireEvent.change(minBuyScoreInput, { target: { value: '3' } });

      expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
    });

    it('should disable submit when value is above 100', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Fill valid data
      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      fireEvent.change(textarea, { target: { value: 'AAPL' } });

      const startDateInput = screen.getByLabelText(/start date/i);
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
      fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

      // Set invalid min buy score
      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;
      fireEvent.change(minBuyScoreInput, { target: { value: '120' } });

      expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
    });

    it('should show dynamic help text based on value', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      const minBuyScoreInput = screen.getByDisplayValue('60') as HTMLInputElement;

      // Test score >= 80
      fireEvent.change(minBuyScoreInput, { target: { value: '80' } });
      expect(screen.getByText(/at least 4 of 5 criteria/i)).toBeInTheDocument();

      // Test score >= 60
      fireEvent.change(minBuyScoreInput, { target: { value: '60' } });
      expect(screen.getByText(/at least 3 of 5 criteria/i)).toBeInTheDocument();

      // Test score >= 40
      fireEvent.change(minBuyScoreInput, { target: { value: '40' } });
      expect(screen.getByText(/at least 2 of 5 criteria/i)).toBeInTheDocument();

      // Test score < 40
      fireEvent.change(minBuyScoreInput, { target: { value: '20' } });
      expect(screen.getByText(/at least 1 of 5 criteria/i)).toBeInTheDocument();
    });
  });

  it('should disable submit when too many symbols', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

    // Create 601 symbols (more than max 600)
    const symbols = Array.from({ length: 601 }, (_, i) => `SYM${i}`).join(', ');

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: symbols } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);
    fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  describe('Stock List Integration', () => {
    it('renders ListSelector component', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);
      expect(screen.getByRole('combobox', { name: /select a stock list/i })).toBeInTheDocument();
    });

    it('populates symbols when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      expect(textarea).toHaveValue('AAPL, MSFT, GOOGL');
    });

    it('shows badge with symbol count when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      expect(screen.getByText('3 symbols from "Tech Stocks"')).toBeInTheDocument();
    });

    it('includes stock_list_id and stock_list_name in submission', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Select stock list
      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      // Fill in dates
      const startDateInput = screen.getByLabelText(/start date/i);
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
      fireEvent.change(endDateInput, { target: { value: '2024-06-01' } });

      // Submit
      await user.click(screen.getByRole('button', { name: /start simulation/i }));

      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          stock_list_id: 1,
          stock_list_name: 'Tech Stocks',
          symbols: ['AAPL', 'MSFT', 'GOOGL'],
          min_buy_score: 60,
        })
      );
    });

    it('clears list reference when "None" is selected but keeps symbols', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Select a list first
      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      expect(textarea).toHaveValue('AAPL, MSFT, GOOGL');

      // Now select "None"
      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'None' }));

      // Symbols should remain but badge should be gone
      expect(textarea).toHaveValue('AAPL, MSFT, GOOGL');
      expect(screen.queryByText(/symbols from/i)).not.toBeInTheDocument();
    });

    it('disables ListSelector during form submission', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={true} />);
      expect(screen.getByRole('combobox', { name: /select a stock list/i })).toBeDisabled();
    });

    it('shows context-aware helper text when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} onSubmitComparison={mockOnSubmitComparison} isLoading={false} />);

      // Before selecting a list - shows symbol count
      expect(screen.getByText(/0 symbols \(max 600\)/i)).toBeInTheDocument();

      // Select a list
      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      // After selecting a list - shows helpful message
      expect(
        screen.getByText('Symbols populated from list. You can modify them before starting.')
      ).toBeInTheDocument();
    });
  });

  describe('Multi-Strategy Selection', () => {
    /** Helper: render the form with valid symbols and dates so the submit button can be enabled */
    const renderWithValidInputs = () => {
      render(
        <ArenaSetupForm
          onSubmit={mockOnSubmit}
          onSubmitComparison={mockOnSubmitComparison}
          isLoading={false}
        />
      );
      fireEvent.change(screen.getByRole('textbox', { name: /symbols/i }), {
        target: { value: 'AAPL' },
      });
      fireEvent.change(screen.getByLabelText(/start date/i), {
        target: { value: '2024-01-01' },
      });
      fireEvent.change(screen.getByLabelText(/end date/i), {
        target: { value: '2024-06-01' },
      });
    };

    it('should show "Start Simulation" button text with 1 strategy selected (default)', () => {
      renderWithValidInputs();
      // Default is ['none'] — 1 strategy
      expect(screen.getByRole('button', { name: /start simulation/i })).toBeEnabled();
    });

    it('should show "Start Comparison (2 strategies)" button text with 2 strategies selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Select a second strategy (Score + Low ATR)
      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));

      expect(
        screen.getByRole('button', { name: /start comparison \(2 strategies\)/i })
      ).toBeEnabled();
    });

    it('should show "Start Comparison (3 strategies)" button text with 3 strategies selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));
      await user.click(screen.getByRole('button', { name: /score \+ high atr/i }));

      expect(
        screen.getByRole('button', { name: /start comparison \(3 strategies\)/i })
      ).toBeEnabled();
    });

    it('should show disabled "Select a Strategy" button when 0 strategies selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Deselect the default 'none' strategy
      await user.click(screen.getByRole('button', { name: /none \(symbol order\)/i }));

      expect(
        screen.getByRole('button', { name: /select a strategy/i })
      ).toBeDisabled();
    });

    it('should revert to "Start Simulation" when deselecting from 2 strategies back to 1', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Add a second strategy
      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));
      expect(
        screen.getByRole('button', { name: /start comparison \(2 strategies\)/i })
      ).toBeEnabled();

      // Deselect the second strategy
      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));
      expect(screen.getByRole('button', { name: /start simulation/i })).toBeEnabled();
    });

    it('should toggle off a strategy when clicking an already-selected one', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      const noneButton = screen.getByRole('button', { name: /none \(symbol order\)/i });
      expect(noneButton).toHaveAttribute('aria-pressed', 'true');

      await user.click(noneButton);
      expect(noneButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('should show portfolio constraint fields when any non-"none" strategy is selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Only 'none' selected by default — constraint fields should NOT appear
      expect(screen.queryByLabelText(/max per sector/i)).not.toBeInTheDocument();

      // Select a non-none strategy
      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));

      expect(screen.getByLabelText(/max per sector/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/max open positions/i)).toBeInTheDocument();
    });

    it('should NOT show portfolio constraint fields when only "none" is selected', async () => {
      renderWithValidInputs();
      // Default is ['none']
      expect(screen.queryByLabelText(/max per sector/i)).not.toBeInTheDocument();
    });

    it('should call onSubmit (not onSubmitComparison) when exactly 1 strategy is selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Default: 1 strategy ('none') selected
      await user.click(screen.getByRole('button', { name: /start simulation/i }));

      expect(mockOnSubmit).toHaveBeenCalledOnce();
      expect(mockOnSubmitComparison).not.toHaveBeenCalled();
    });

    it('should call onSubmitComparison (not onSubmit) when 2+ strategies are selected', async () => {
      const user = userEvent.setup();
      renderWithValidInputs();

      // Add a second strategy
      await user.click(screen.getByRole('button', { name: /score \+ low atr/i }));

      await user.click(
        screen.getByRole('button', { name: /start comparison \(2 strategies\)/i })
      );

      expect(mockOnSubmitComparison).toHaveBeenCalledOnce();
      expect(mockOnSubmit).not.toHaveBeenCalled();
      expect(mockOnSubmitComparison).toHaveBeenCalledWith(
        expect.objectContaining({
          portfolio_strategies: ['none', 'score_sector_low_atr'],
        })
      );
    });

    it('should initialize selectedStrategies from initialValues.portfolio_strategy', () => {
      render(
        <ArenaSetupForm
          onSubmit={mockOnSubmit}
          onSubmitComparison={mockOnSubmitComparison}
          isLoading={false}
          initialValues={{
            symbols: ['AAPL'],
            start_date: '2024-01-01',
            end_date: '2024-06-01',
            initial_capital: 10000,
            position_size: 1000,
            trailing_stop_pct: 5,
            min_buy_score: 60,
            portfolio_strategy: 'score_sector_low_atr',
          }}
        />
      );

      const lowAtrButton = screen.getByRole('button', { name: /score \+ low atr/i });
      expect(lowAtrButton).toHaveAttribute('aria-pressed', 'true');

      const noneButton = screen.getByRole('button', { name: /none \(symbol order\)/i });
      expect(noneButton).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('initialValues (replay feature)', () => {
    it('should populate form fields from initialValues', () => {
      const initialValues = {
        symbols: ['AAPL', 'NVDA', 'TSLA'],
        start_date: '2025-01-01',
        end_date: '2025-12-31',
        initial_capital: 50000,
        position_size: 2500,
        trailing_stop_pct: 8,
        min_buy_score: 80,
        stock_list_id: 1,
        stock_list_name: 'Tech Stocks',
      };

      render(
        <ArenaSetupForm
          onSubmit={mockOnSubmit}
          onSubmitComparison={mockOnSubmitComparison}
          isLoading={false}
          initialValues={initialValues}
        />
      );

      // Verify symbols textarea contains the values
      const symbolsInput = screen.getByRole('textbox', { name: /symbols/i });
      expect(symbolsInput).toHaveValue('AAPL, NVDA, TSLA');

      // Verify dates
      const startDateInput = screen.getByLabelText(/start date/i);
      expect(startDateInput).toHaveValue('2025-01-01');

      const endDateInput = screen.getByLabelText(/end date/i);
      expect(endDateInput).toHaveValue('2025-12-31');

      // Verify capital fields
      const capitalInput = screen.getByLabelText(/capital \(\$\)/i) as HTMLInputElement;
      expect(capitalInput.value).toBe('50000');

      const positionSizeInput = screen.getByLabelText(/position size/i) as HTMLInputElement;
      expect(positionSizeInput.value).toBe('2500');

      // Verify trailing stop
      const trailingStopInput = screen.getByLabelText(/trailing stop/i) as HTMLInputElement;
      expect(trailingStopInput.value).toBe('8');

      // Verify min buy score
      const minBuyScoreInput = screen.getByDisplayValue('80') as HTMLInputElement;
      expect(minBuyScoreInput).toHaveAttribute('id', 'arena-min-buy-score-input');
    });

    it('should handle null stock_list_id gracefully', () => {
      const initialValues = {
        symbols: ['AAPL'],
        start_date: '2025-01-01',
        end_date: '2025-12-31',
        initial_capital: 10000,
        position_size: 1000,
        trailing_stop_pct: 5,
        min_buy_score: 60,
        stock_list_id: null,
        stock_list_name: null,
      };

      render(
        <ArenaSetupForm
          onSubmit={mockOnSubmit}
          onSubmitComparison={mockOnSubmitComparison}
          isLoading={false}
          initialValues={initialValues}
        />
      );

      // Form should render without errors
      const symbolsInput = screen.getByRole('textbox', { name: /symbols/i });
      expect(symbolsInput).toHaveValue('AAPL');

      // List selector should show default state (no list selected)
      expect(screen.queryByText(/symbols from/i)).not.toBeInTheDocument();
    });

    it('should allow modifying pre-populated values before submission', async () => {
      const initialValues = {
        symbols: ['AAPL', 'NVDA'],
        start_date: '2025-01-01',
        end_date: '2025-06-30',
        initial_capital: 10000,
        position_size: 1000,
        trailing_stop_pct: 5,
        min_buy_score: 60,
        stock_list_id: null,
        stock_list_name: null,
      };

      render(
        <ArenaSetupForm
          onSubmit={mockOnSubmit}
          onSubmitComparison={mockOnSubmitComparison}
          isLoading={false}
          initialValues={initialValues}
        />
      );

      // Modify the end date
      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(endDateInput, { target: { value: '2025-12-31' } });

      // Submit
      const submitButton = screen.getByRole('button', { name: /start simulation/i });
      fireEvent.click(submitButton);

      // Verify submission includes modified value
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          symbols: ['AAPL', 'NVDA'],
          start_date: '2025-01-01',
          end_date: '2025-12-31', // Modified value
          initial_capital: 10000,
          position_size: 1000,
          trailing_stop_pct: 5,
          min_buy_score: 60,
        })
      );
    });
  });
});
