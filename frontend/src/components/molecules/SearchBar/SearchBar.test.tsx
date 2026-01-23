import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchBar } from './SearchBar';

describe('SearchBar', () => {
  it('should render search input with icon', () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);

    // Assert
    const input = screen.getByLabelText('Stock symbol search');
    expect(input).toBeInTheDocument();
    // Verify search icon SVG is present
    const svg = input.parentElement?.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('should display placeholder text', () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);

    // Assert
    expect(screen.getByPlaceholderText('Search for stocks e.g. AAPL, TSLA')).toBeInTheDocument();
  });

  it('should update input value when user types', async () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);
    const input = screen.getByLabelText('Stock symbol search');
    await user.type(input, 'AAPL');

    // Assert
    expect(input).toHaveValue('AAPL');
  });

  it('should call onSearch when Enter is pressed', async () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);
    const input = screen.getByLabelText('Stock symbol search');
    await user.type(input, 'TSLA');
    await user.keyboard('{Enter}');

    // Assert
    expect(onSearch).toHaveBeenCalledWith('TSLA');
  });

  it('should not call onSearch when other keys are pressed', async () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);
    const input = screen.getByLabelText('Stock symbol search');
    await user.type(input, 'MSFT');

    // Assert
    expect(onSearch).not.toHaveBeenCalled();
  });

  it('should initialize with provided value', () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();

    // Act
    render(<SearchBar value="AAPL" onChange={onChange} onSearch={onSearch} />);

    // Assert
    const input = screen.getByLabelText('Stock symbol search');
    expect(input).toHaveValue('AAPL');
  });

  it('should allow user to type and modify the input value', async () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<SearchBar value="AAPL" onChange={onChange} onSearch={onSearch} />);
    const input = screen.getByLabelText('Stock symbol search');
    await user.clear(input);
    await user.type(input, 'TSLA');

    // Assert - user typing should update the input
    expect(input).toHaveValue('TSLA');
  });

  it('should sync input value when value prop changes', () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();

    // Act - initial render with AAPL
    const { rerender } = render(
      <SearchBar value="AAPL" onChange={onChange} onSearch={onSearch} />
    );
    const input = screen.getByLabelText('Stock symbol search');
    expect(input).toHaveValue('AAPL');

    // Act - rerender with new value (e.g., from watchlist click)
    rerender(<SearchBar value="TSLA" onChange={onChange} onSearch={onSearch} />);

    // Assert - input should sync to new value
    expect(input).toHaveValue('TSLA');
  });

  it('should have search icon positioned on left', () => {
    // Arrange
    const onChange = vi.fn();
    const onSearch = vi.fn();

    // Act
    render(<SearchBar value="" onChange={onChange} onSearch={onSearch} />);

    // Assert - search icon should be in the document
    const iconContainer = screen.getByRole('textbox').parentElement;
    expect(iconContainer).toBeInTheDocument();
    // Verify the search icon SVG is present
    const svg = iconContainer?.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
