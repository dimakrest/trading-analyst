import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WatchlistHeader } from '../WatchlistHeader';
import type { StockList } from '@/services/stockListService';

describe('WatchlistHeader', () => {
  const mockLists: StockList[] = [
    { id: 1, name: 'Tech Leaders', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
    { id: 2, name: 'Growth Stocks', symbols: ['NVDA', 'TSLA'], symbol_count: 2 },
    { id: 3, name: 'Dividend Plays', symbols: ['KO', 'JNJ'], symbol_count: 2 },
  ];

  it('should render the WATCHLIST title', () => {
    // Arrange
    const onListChange = vi.fn();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    // Assert
    expect(screen.getByText('Watchlist')).toBeInTheDocument();
  });

  it('should render select trigger with aria-label', () => {
    // Arrange
    const onListChange = vi.fn();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    // Assert
    expect(screen.getByLabelText('Select a watchlist')).toBeInTheDocument();
  });

  it('should show placeholder when no list is selected', () => {
    // Arrange
    const onListChange = vi.fn();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    // Assert
    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveTextContent('Select a list');
  });

  it('should show list options when dropdown is opened', async () => {
    // Arrange
    const onListChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    await user.click(screen.getByRole('combobox'));

    // Assert
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Tech Leaders' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Growth Stocks' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Dividend Plays' })).toBeInTheDocument();
    });
  });

  it('should call onListChange with list id when option is selected', async () => {
    // Arrange
    const onListChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    await user.click(screen.getByRole('combobox'));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Tech Leaders' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Tech Leaders' }));

    // Assert
    await waitFor(() => {
      expect(onListChange).toHaveBeenCalledWith(1);
    });
  });

  it('should display selected list name in trigger', () => {
    // Arrange
    const onListChange = vi.fn();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={1}
        onListChange={onListChange}
      />
    );

    // Assert
    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveTextContent('Tech Leaders');
  });

  it('should render with empty list array and show message', async () => {
    // Arrange
    const onListChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistHeader
        lists={[]}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    await user.click(screen.getByRole('combobox'));

    // Assert
    await waitFor(() => {
      expect(screen.getByText('No lists available')).toBeInTheDocument();
    });
  });

  it('should have proper styling classes on title', () => {
    // Arrange
    const onListChange = vi.fn();

    // Act
    render(
      <WatchlistHeader
        lists={mockLists}
        selectedListId={null}
        onListChange={onListChange}
      />
    );

    // Assert
    const title = screen.getByText('Watchlist');
    expect(title).toHaveClass('uppercase');
    expect(title).toHaveClass('text-text-muted');
  });
});
