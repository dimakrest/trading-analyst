import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SymbolChips } from './SymbolChips';

describe('SymbolChips', () => {
  const mockSymbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'];

  it('should render all symbol chips', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    mockSymbols.forEach((symbol) => {
      expect(screen.getByRole('button', { name: new RegExp(symbol) })).toBeInTheDocument();
    });
  });

  it('should render "Quick Switch" label', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByText('Quick Switch')).toBeInTheDocument();
  });

  it('should highlight active symbol with aria-pressed', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="MSFT"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    const activeButton = screen.getByRole('button', { name: /MSFT/i });
    expect(activeButton).toHaveAttribute('aria-pressed', 'true');

    // Other buttons should not have aria-pressed="true"
    const inactiveButton = screen.getByRole('button', { name: /AAPL/i });
    expect(inactiveButton).toHaveAttribute('aria-pressed', 'false');
  });

  it('should call onSymbolSelect when chip is clicked', async () => {
    // Arrange
    const onSymbolSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    await user.click(screen.getByRole('button', { name: /GOOGL/i }));

    // Assert
    expect(onSymbolSelect).toHaveBeenCalledWith('GOOGL');
  });

  it('should call onSymbolSelect when already-active chip is clicked', async () => {
    // Arrange
    const onSymbolSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    await user.click(screen.getByRole('button', { name: /AAPL/i }));

    // Assert - should still call the handler
    expect(onSymbolSelect).toHaveBeenCalledWith('AAPL');
  });

  it('should handle case-insensitive active symbol matching', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act - activeSymbol in lowercase
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="aapl"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert - AAPL should still be marked as active
    const activeButton = screen.getByRole('button', { name: /AAPL/i });
    expect(activeButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('should render with single symbol', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={['AAPL']}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByRole('button', { name: /AAPL/i })).toBeInTheDocument();
  });

  it('should have role="group" for accessibility', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByRole('group', { name: 'Symbol quick switch' })).toBeInTheDocument();
  });

  it('should have descriptive aria-label on each chip', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    expect(screen.getByLabelText('Switch to AAPL (currently selected)')).toBeInTheDocument();
    expect(screen.getByLabelText('Switch to MSFT')).toBeInTheDocument();
  });

  it('should apply different styles to active vs inactive chips', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert
    const activeChip = screen.getByRole('button', { name: /AAPL/i });
    const inactiveChip = screen.getByRole('button', { name: /MSFT/i });

    // Active chip should have primary background classes
    expect(activeChip.className).toContain('bg-primary');

    // Inactive chip should have muted background classes
    expect(inactiveChip.className).toContain('bg-muted');
  });

  it('should be keyboard accessible', async () => {
    // Arrange
    const onSymbolSelect = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="AAPL"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Tab to the first chip
    await user.tab();

    // Assert - first button should be focused
    const firstButton = screen.getByRole('button', { name: /AAPL/i });
    expect(firstButton).toHaveFocus();

    // Press Enter to select
    await user.keyboard('{Enter}');
    expect(onSymbolSelect).toHaveBeenCalledWith('AAPL');
  });

  it('should handle non-matching active symbol gracefully', () => {
    // Arrange
    const onSymbolSelect = vi.fn();

    // Act - activeSymbol that doesn't exist in symbols
    render(
      <SymbolChips
        symbols={mockSymbols}
        activeSymbol="NONEXISTENT"
        onSymbolSelect={onSymbolSelect}
      />
    );

    // Assert - all chips should be inactive
    mockSymbols.forEach((symbol) => {
      const button = screen.getByRole('button', { name: new RegExp(symbol) });
      expect(button).toHaveAttribute('aria-pressed', 'false');
    });
  });
});
