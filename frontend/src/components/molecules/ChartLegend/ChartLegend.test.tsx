import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChartLegend } from './ChartLegend';

describe('ChartLegend', () => {
  it('should render all legend items', () => {
    // Arrange & Act
    render(<ChartLegend />);

    // Assert
    expect(screen.getByText(/bullish/i)).toBeInTheDocument();
    expect(screen.getByText(/bearish/i)).toBeInTheDocument();
    expect(screen.getByText(/MA 20/i)).toBeInTheDocument();
    expect(screen.getByText(/wicks/i)).toBeInTheDocument();
    expect(screen.getByText(/CCI/)).toBeInTheDocument();
  });

  it('should have accessible list structure', () => {
    // Arrange & Act
    render(<ChartLegend />);

    // Assert
    const legend = screen.getByRole('list', { name: /chart color legend/i });
    expect(legend).toBeInTheDocument();
  });

  it('should apply custom className', () => {
    // Arrange & Act
    const { container } = render(<ChartLegend className="custom-class" />);

    // Assert
    expect(container.firstChild).toHaveClass('custom-class');
  });
});
