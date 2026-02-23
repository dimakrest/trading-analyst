import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ArenaSetupForm } from './ArenaSetupForm';
import { usePortfolioConfigs } from '../../hooks/usePortfolioConfigs';

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

vi.mock('../../hooks/usePortfolioConfigs', () => ({
  usePortfolioConfigs: vi.fn(() => ({
    configs: [],
    setConfigs: vi.fn(),
    isLoading: false,
    error: null,
  })),
}));

const defaultPortfolioConfigs = [
  {
    id: 1,
    name: 'Default Setup',
    portfolio_strategy: 'score_sector_moderate_atr',
    position_size: 1000,
    min_buy_score: 60,
    trailing_stop_pct: 5,
    max_per_sector: 2,
    max_open_positions: 8,
  },
];

describe('ArenaSetupForm', () => {
  const mockOnSubmit = vi.fn();
  const mockUsePortfolioConfigs = vi.mocked(usePortfolioConfigs);

  beforeEach(() => {
    mockOnSubmit.mockClear();
    mockUsePortfolioConfigs.mockReturnValue({
      configs: defaultPortfolioConfigs,
      setConfigs: vi.fn(),
      isLoading: false,
      error: null,
    });
  });

  it('should render with empty state', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    expect(screen.getByRole('textbox', { name: /symbols/i })).toBeInTheDocument();
    expect(screen.getByText(/0 symbols/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should show symbol count when symbols are entered', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, NVDA, TSLA' } });

    expect(screen.getByText(/3 symbols/i)).toBeInTheDocument();
  });

  it('should parse symbols separated by comma, space, or newline', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL\nNVDA TSLA,AMD' } });

    expect(screen.getByText(/4 symbols/i)).toBeInTheDocument();
  });

  it('should uppercase symbols automatically', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'aapl, nvda' } });

    expect(screen.getByText(/2 symbols/i)).toBeInTheDocument();
  });

  it('should filter out invalid symbols', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    // Empty strings and very long symbols should be filtered out
    fireEvent.change(textarea, { target: { value: 'AAPL, , VERYLONGSYMBOLNAME, NVDA' } });

    expect(screen.getByText(/2 symbols/i)).toBeInTheDocument();
  });

  it('should have disabled submit button when no dates entered', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL, NVDA' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should have disabled submit button when start date is after end date', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);

    fireEvent.change(startDateInput, { target: { value: '2024-01-15' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-01' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should enable submit button with valid inputs', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox', { name: /symbols/i });
    fireEvent.change(textarea, { target: { value: 'AAPL' } });

    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);

    fireEvent.change(startDateInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endDateInput, { target: { value: '2024-01-15' } });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeEnabled();
  });

  it('should keep submit disabled when no portfolio setups exist', () => {
    mockUsePortfolioConfigs.mockReturnValue({
      configs: [],
      setConfigs: vi.fn(),
      isLoading: false,
      error: null,
    });
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    fireEvent.change(screen.getByRole('textbox', { name: /symbols/i }), {
      target: { value: 'AAPL' },
    });
    fireEvent.change(screen.getByLabelText(/start date/i), {
      target: { value: '2024-01-01' },
    });
    fireEvent.change(screen.getByLabelText(/end date/i), {
      target: { value: '2024-01-15' },
    });

    expect(screen.getByRole('button', { name: /start simulation/i })).toBeDisabled();
  });

  it('should call onSubmit with parsed data when form is submitted', async () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

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
        portfolio_config_id: 1,
      })
    );
  });

  it('should submit portfolio_config_id when a saved setup is selected', async () => {
    const user = userEvent.setup();
    mockUsePortfolioConfigs.mockReturnValue({
      configs: [
        {
          id: 7,
          name: 'Conservative',
          portfolio_strategy: 'score_sector_low_atr',
          position_size: 2200,
          min_buy_score: 75,
          trailing_stop_pct: 8.5,
          max_per_sector: 1,
          max_open_positions: 4,
        },
      ],
      setConfigs: vi.fn(),
      isLoading: false,
      error: null,
    });

    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    await user.click(screen.getByRole('combobox', { name: /saved setup/i }));
    await user.click(screen.getByRole('option', { name: 'Conservative' }));

    fireEvent.change(screen.getByRole('textbox', { name: /symbols/i }), {
      target: { value: 'AAPL' },
    });
    fireEvent.change(screen.getByLabelText(/start date/i), {
      target: { value: '2024-01-01' },
    });
    fireEvent.change(screen.getByLabelText(/end date/i), {
      target: { value: '2024-01-15' },
    });

    await user.click(screen.getByRole('button', { name: /start simulation/i }));

    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        portfolio_config_id: 7,
      })
    );
  });

  it('should disable form when loading', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={true} />);

    expect(screen.getByRole('textbox', { name: /symbols/i })).toBeDisabled();
    expect(screen.getByLabelText(/start date/i)).toBeDisabled();
    expect(screen.getByLabelText(/end date/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
  });

  it('should show agent configuration section', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    expect(screen.getByText(/agent configuration/i)).toBeInTheDocument();
    expect(screen.getByText(/live20 mean reversion/i)).toBeInTheDocument();
  });

  it('should have default values for capital settings', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

    const capitalInput = screen.getByLabelText(/capital \(\$\)/i) as HTMLInputElement;
    expect(capitalInput.value).toBe('10000');
  });

  describe('Portfolio-managed settings', () => {
    it('should show setup summary from selected portfolio config', () => {
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

      expect(screen.getByText(/using "default setup"/i)).toBeInTheDocument();
      expect(screen.getByText(/min score: 60/i)).toBeInTheDocument();
      expect(screen.getByText(/stop: 5%/i)).toBeInTheDocument();
    });
  });

  it('should disable submit when too many symbols', () => {
    render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

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
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);
      expect(screen.getByRole('combobox', { name: /select a stock list/i })).toBeInTheDocument();
    });

    it('populates symbols when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      const textarea = screen.getByRole('textbox', { name: /symbols/i });
      expect(textarea).toHaveValue('AAPL, MSFT, GOOGL');
    });

    it('shows badge with symbol count when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

      await user.click(screen.getByRole('combobox', { name: /select a stock list/i }));
      await user.click(screen.getByRole('option', { name: 'Tech Stocks' }));

      expect(screen.getByText('3 symbols from "Tech Stocks"')).toBeInTheDocument();
    });

    it('includes stock_list_id and stock_list_name in submission', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

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
          portfolio_config_id: 1,
        })
      );
    });

    it('clears list reference when "None" is selected but keeps symbols', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

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
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={true} />);
      expect(screen.getByRole('combobox', { name: /select a stock list/i })).toBeDisabled();
    });

    it('shows context-aware helper text when list is selected', async () => {
      const user = userEvent.setup();
      render(<ArenaSetupForm onSubmit={mockOnSubmit} isLoading={false} />);

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
          portfolio_config_id: 1,
        })
      );
    });
  });
});
