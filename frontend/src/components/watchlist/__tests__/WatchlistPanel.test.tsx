import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WatchlistPanel } from '../WatchlistPanel';
import type { StockList } from '@/services/stockListService';

describe('WatchlistPanel', () => {
  const mockLists: StockList[] = [
    { id: 1, name: 'Tech Leaders', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
    { id: 2, name: 'Growth Stocks', symbols: ['NVDA', 'TSLA'], symbol_count: 2 },
  ];

  const mockSymbols = ['AAPL', 'MSFT', 'GOOGL'];

  it('should render WatchlistHeader', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByText('Watchlist')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('should render all symbols from the list', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
  });

  it('should highlight the selected symbol', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol="MSFT"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    const msftButton = screen.getByLabelText('Select MSFT');
    const aaplButton = screen.getByLabelText('Select AAPL');

    expect(msftButton).toHaveClass('bg-accent-primary-muted');
    expect(aaplButton).not.toHaveClass('bg-accent-primary-muted');
  });

  it('should call onSymbolSelect when a symbol is clicked', async () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    await user.click(screen.getByLabelText('Select AAPL'));

    // Assert
    expect(onSymbolSelect).toHaveBeenCalledWith('AAPL');
  });

  it('should call onListChange when a list is selected', async () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Growth Stocks' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Growth Stocks' }));

    // Assert
    await waitFor(() => {
      expect(onListChange).toHaveBeenCalledWith(2);
    });
  });

  it('should show loading skeleton when isLoading is true', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={[]}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
        isLoading={true}
      />
    );

    // Assert
    expect(screen.getByTestId('watchlist-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-items')).not.toBeInTheDocument();
  });

  it('should show empty state message when no list is selected', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
        symbols={[]}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument();
    expect(screen.getByText('Select a list to view symbols')).toBeInTheDocument();
  });

  it('should show empty state message when list has no symbols', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={[]}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByTestId('watchlist-empty')).toBeInTheDocument();
    expect(screen.getByText('No symbols in this list')).toBeInTheDocument();
  });

  it('should have proper background styling', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    const { container } = render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    const panel = container.firstChild as HTMLElement;
    expect(panel).toHaveClass('bg-bg-secondary');
    expect(panel).toHaveClass('border-r');
    expect(panel).toHaveClass('border-subtle');
  });

  it('should render items container when symbols are provided', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByTestId('watchlist-items')).toBeInTheDocument();
  });

  it('should have fixed height calculated from viewport', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();

    // Act
    const { container } = render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={mockSymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    const panel = container.firstChild as HTMLElement;
    expect(panel).toHaveStyle({ height: 'calc(100vh - var(--status-bar-height))' });
  });

  it('should handle many symbols with scroll area', () => {
    // Arrange
    const onListChange = vi.fn();
    const onSymbolSelect = vi.fn();
    const manySymbols = Array.from({ length: 50 }, (_, i) => `SYM${i}`);

    // Act
    render(
      <WatchlistPanel
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
        symbols={manySymbols}
        selectedSymbol={null}
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert - all symbols should be rendered (ScrollArea handles overflow)
    expect(screen.getByText('SYM0')).toBeInTheDocument();
    expect(screen.getByText('SYM49')).toBeInTheDocument();
  });
});
