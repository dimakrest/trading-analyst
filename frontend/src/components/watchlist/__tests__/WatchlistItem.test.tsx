import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WatchlistItem } from '../WatchlistItem';

describe('WatchlistItem', () => {
  it('should render symbol', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  it('should apply active styles when isActive is true', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={true}
        onClick={onClick}
      />
    );

    // Assert
    const button = screen.getByRole('button');
    expect(button).toHaveClass('bg-accent-primary-muted');
    expect(button).toHaveClass('border-accent-primary');
  });

  it('should not apply active styles when isActive is false', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    const button = screen.getByRole('button');
    expect(button).not.toHaveClass('bg-accent-primary-muted');
    expect(button).not.toHaveClass('border-accent-primary');
  });

  it('should call onClick when clicked', async () => {
    // Arrange
    const onClick = vi.fn();
    const user = userEvent.setup();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    await user.click(screen.getByRole('button'));

    // Assert
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('should have proper aria-label for accessibility', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    expect(screen.getByLabelText('Select AAPL')).toBeInTheDocument();
  });

  it('should have aria-pressed attribute matching isActive state', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    const { rerender } = render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false');

    // Re-render with active state
    rerender(
      <WatchlistItem
        symbol="AAPL"
        isActive={true}
        onClick={onClick}
      />
    );

    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('should apply hover class on the button', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    const button = screen.getByRole('button');
    expect(button).toHaveClass('hover:bg-bg-tertiary');
  });

  it('should have font-mono class on symbol', () => {
    // Arrange
    const onClick = vi.fn();

    // Act
    render(
      <WatchlistItem
        symbol="AAPL"
        isActive={false}
        onClick={onClick}
      />
    );

    // Assert
    const symbolElement = screen.getByText('AAPL');
    expect(symbolElement).toHaveClass('font-mono');
    expect(symbolElement).toHaveClass('font-bold');
  });
});
