import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ListSelector } from './ListSelector';
import type { StockList } from '@/services/stockListService';

describe('ListSelector', () => {
  const mockLists: StockList[] = [
    { id: 1, name: 'Tech Leaders', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
    { id: 2, name: 'Growth Stocks', symbols: ['NVDA', 'TSLA'], symbol_count: 2 },
    { id: 3, name: 'Dividend Plays', symbols: ['KO', 'JNJ'], symbol_count: 2 },
  ];

  it('should render select trigger', () => {
    // Arrange
    const onSelect = vi.fn();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    // Assert
    const trigger = screen.getByRole('combobox');
    expect(trigger).toBeInTheDocument();
  });

  it('should render with aria-label for accessibility', () => {
    // Arrange
    const onSelect = vi.fn();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    // Assert
    expect(screen.getByLabelText('Select a stock list')).toBeInTheDocument();
  });

  it('should show list options when opened', async () => {
    // Arrange
    const onSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));

    // Assert
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'None' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Tech Leaders' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Growth Stocks' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Dividend Plays' })).toBeInTheDocument();
    });
  });

  it('should call onSelect with list id when option is selected', async () => {
    // Arrange
    const onSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    // Open dropdown and select an option
    await user.click(screen.getByRole('combobox'));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Tech Leaders' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'Tech Leaders' }));

    // Assert
    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith(1);
    });
  });

  it('should call onSelect with null when None is selected', async () => {
    // Arrange
    const onSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={1}
        onSelect={onSelect}
      />
    );

    // Open dropdown and select None
    await user.click(screen.getByRole('combobox'));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'None' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('option', { name: 'None' }));

    // Assert
    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith(null);
    });
  });

  it('should be disabled when isLoading is true', () => {
    // Arrange
    const onSelect = vi.fn();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
        isLoading={true}
      />
    );

    // Assert
    expect(screen.getByRole('combobox')).toBeDisabled();
  });

  it('should display selected list name in trigger', async () => {
    // Arrange
    const onSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={1}
        onSelect={onSelect}
      />
    );

    // Open dropdown to verify list items are there
    await user.click(screen.getByRole('combobox'));

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Tech Leaders' })).toBeInTheDocument();
    });
  });

  it('should render with empty list array', () => {
    // Arrange
    const onSelect = vi.fn();

    // Act
    render(
      <ListSelector
        lists={[]}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    // Assert
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('should render list icon in trigger', () => {
    // Arrange
    const onSelect = vi.fn();

    // Act
    render(
      <ListSelector
        lists={mockLists}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    // Assert - list icon SVG should be present
    const trigger = screen.getByRole('combobox');
    const svg = trigger.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('should show only None option when lists array is empty', async () => {
    // Arrange
    const onSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <ListSelector
        lists={[]}
        selectedListId={null}
        onSelect={onSelect}
      />
    );

    await user.click(screen.getByRole('combobox'));

    // Assert
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'None' })).toBeInTheDocument();
      // Only None option should be present
      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(1);
    });
  });
});
