import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MultiListSelector } from './MultiListSelector';

const mockLists = [
  { id: 1, name: 'Tech Leaders', symbol_count: 25, symbols: [] },
  { id: 2, name: 'Healthcare', symbol_count: 30, symbols: [] },
  { id: 3, name: 'Energy', symbol_count: 15, symbols: [] },
];

describe('MultiListSelector', () => {
  it('should render with placeholder when no lists selected', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    // Assert
    expect(screen.getByText('Select lists...')).toBeInTheDocument();
  });

  it('should show selected count when lists are selected', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1, 2]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={50}
      />
    );

    // Assert
    expect(screen.getByText('2 lists selected')).toBeInTheDocument();
    expect(screen.getByText('50/500')).toBeInTheDocument();
  });

  it('should call onSelectionChange when list is toggled', async () => {
    // Arrange
    const onSelectionChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={onSelectionChange}
        uniqueSymbolCount={0}
      />
    );

    // Open dropdown
    await user.click(screen.getByRole('button'));

    // Wait for dropdown content
    await waitFor(() => {
      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
    });

    // Click on a list item
    await user.click(screen.getByText('Tech Leaders'));

    // Assert
    expect(onSelectionChange).toHaveBeenCalledWith([1]);
  });

  it('should show warning color when near limit', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={460}
        maxSymbols={500}
      />
    );

    // Assert - should have amber warning styling
    const badge = screen.getByText('460/500');
    expect(badge).toHaveClass('text-[#fbbf24]');
  });

  it('should show error color when over limit', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={520}
        maxSymbols={500}
      />
    );

    // Assert - should have destructive styling
    const badge = screen.getByText('520/500');
    expect(badge).toHaveClass('text-destructive');
  });

  it('should clear all selections when clear button clicked', async () => {
    // Arrange
    const onSelectionChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1, 2]}
        onSelectionChange={onSelectionChange}
        uniqueSymbolCount={50}
      />
    );

    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Clear all')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Clear all'));

    // Assert
    expect(onSelectionChange).toHaveBeenCalledWith([]);
  });

  it('should show "1 list selected" for singular case', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={25}
      />
    );

    // Assert
    expect(screen.getByText('1 list selected')).toBeInTheDocument();
  });

  it('should display loading state', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
        isLoading={true}
      />
    );

    // Assert
    expect(screen.getByText('Loading lists...')).toBeInTheDocument();
  });

  it('should display "No lists available" when lists array is empty', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={[]}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    await waitFor(() => {
      expect(screen.getByText('No lists available')).toBeInTheDocument();
    });
  });

  it('should deselect a list when already selected', async () => {
    // Arrange
    const onSelectionChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1, 2]}
        onSelectionChange={onSelectionChange}
        uniqueSymbolCount={55}
      />
    );

    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Tech Leaders')).toBeInTheDocument();
    });

    // Deselect first list
    await user.click(screen.getByText('Tech Leaders'));

    // Assert
    expect(onSelectionChange).toHaveBeenCalledWith([2]);
  });

  it('should show symbol counts for each list in dropdown', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    await waitFor(() => {
      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument();
      expect(screen.getByText('15')).toBeInTheDocument();
    });
  });

  it('should have proper aria-label on trigger button', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={25}
      />
    );

    // Assert
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', '1 list selected with 25 unique symbols');
  });

  it('should have proper aria-label on list items', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    await waitFor(() => {
      const techLeadersItem = screen.getByLabelText('Tech Leaders with 25 symbols');
      expect(techLeadersItem).toBeInTheDocument();
    });
  });

  it('should use custom maxSymbols when provided', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={100}
        maxSymbols={200}
      />
    );

    // Assert
    expect(screen.getByText('100/200')).toBeInTheDocument();
  });

  it('should show normal badge color when well below limit', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={100}
        maxSymbols={500}
      />
    );

    // Assert
    const badge = screen.getByText('100/500');
    expect(badge).toHaveClass('text-[#c4b5fd]');
  });

  it('should not show badge when no lists selected', () => {
    // Arrange & Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    // Assert
    expect(screen.queryByText(/\/500/)).not.toBeInTheDocument();
  });

  it('should show "Select all" button when no lists are selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    await waitFor(() => {
      expect(screen.getByText('Select all')).toBeInTheDocument();
    });
  });

  it('should show "Select all" button when some lists are selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={25}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert - both buttons should be visible
    await waitFor(() => {
      expect(screen.getByText('Select all')).toBeInTheDocument();
      expect(screen.getByText('Clear all')).toBeInTheDocument();
    });
  });

  it('should hide "Select all" button when all lists are selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[1, 2, 3]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={70}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert - only Clear all should be visible
    await waitFor(() => {
      expect(screen.queryByText('Select all')).not.toBeInTheDocument();
      expect(screen.getByText('Clear all')).toBeInTheDocument();
    });
  });

  it('should select all lists when "Select all" is clicked', async () => {
    // Arrange
    const onSelectionChange = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={mockLists}
        selectedListIds={[]}
        onSelectionChange={onSelectionChange}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Select all')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Select all'));

    // Assert
    expect(onSelectionChange).toHaveBeenCalledWith([1, 2, 3]);
  });

  it('should not show "Select all" when lists array is empty', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(
      <MultiListSelector
        lists={[]}
        selectedListIds={[]}
        onSelectionChange={vi.fn()}
        uniqueSymbolCount={0}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    await waitFor(() => {
      expect(screen.queryByText('Select all')).not.toBeInTheDocument();
    });
  });
});
