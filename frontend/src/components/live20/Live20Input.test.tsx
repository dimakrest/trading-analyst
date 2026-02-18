import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Live20Input } from './Live20Input';
import * as useStockListsModule from '@/hooks/useStockLists';

// Mock the useStockLists hook
vi.mock('@/hooks/useStockLists');

const mockLists = [
  { id: 1, name: 'Tech Watchlist', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
  { id: 2, name: 'Energy Stocks', symbols: ['XOM', 'CVX'], symbol_count: 2 },
  { id: 3, name: 'Empty List', symbols: [], symbol_count: 0 },
];

/**
 * Helper to get the multi-list selector button.
 */
const getMultiListSelectorButton = () => {
  return screen.getByRole('button', { name: /Select (stock )?lists|selected/i });
};

/** Default props required by the component beyond the ones under test */
const defaultProps = {
  agentConfigs: [],
  onAgentConfigChange: vi.fn(),
};

describe('Live20Input', () => {
  beforeEach(() => {
    vi.mocked(useStockListsModule.useStockLists).mockReturnValue({
      lists: mockLists,
      isLoading: false,
      error: null,
      createList: vi.fn(),
      updateList: vi.fn(),
      deleteList: vi.fn(),
      refetch: vi.fn(),
    });
  });

  it('should populate textarea when a list is selected', async () => {
    // Arrange
    const onAnalyze = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

    // Open the multi-list selector and select Tech Watchlist
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown before checking textarea (dropdown uses portal and marks content aria-hidden)
    await user.keyboard('{Escape}');

    // Assert - Verify textarea is populated (sorted alphabetically)
    await waitFor(() => {
      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveValue('AAPL, GOOGL, MSFT');
    });
  });

  it('should pass sourceLists to onAnalyze callback', async () => {
    // Arrange
    const onAnalyze = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

    // Select a list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown before checking textarea
    await user.keyboard('{Escape}');

    // Wait for textarea to be populated (sorted)
    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
    });

    // Click analyze
    await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

    // Assert - should pass sourceLists array
    await waitFor(() => {
      expect(onAnalyze).toHaveBeenCalledWith(
        ['AAPL', 'GOOGL', 'MSFT'],
        [{ id: 1, name: 'Tech Watchlist' }]
      );
    });
  });

  it('should allow manual symbol entry without list selection', async () => {
    // Arrange
    const onAnalyze = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

    // Type symbols manually
    await user.type(screen.getByRole('textbox'), 'NVDA, AMD');
    await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

    // Assert
    await waitFor(() => {
      expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD'], null);
    });
  });

  it('should show combined info banner when multiple lists are selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    // Select first list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown before reopening
    await user.keyboard('{Escape}');

    // Reopen dropdown and select second list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Energy Stocks/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Energy Stocks/i }));

    // Close the dropdown
    await user.keyboard('{Escape}');

    // Assert - should show info banner with combined count
    await waitFor(() => {
      expect(screen.getByText(/Combined 2 lists/)).toBeInTheDocument();
    });
  });

  it('should not populate textarea when empty list is selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Empty List/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Empty List/i }));

    // Close dropdown before checking textarea
    await user.keyboard('{Escape}');

    // Assert - textarea should remain empty
    await waitFor(() => {
      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveValue('');
    });
  });

  it('should combine symbols when multiple lists are selected', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    // Select first list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown after first selection
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
    });

    // Add second list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Energy Stocks/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Energy Stocks/i }));

    // Close dropdown
    await user.keyboard('{Escape}');

    // Assert - symbols should be combined and deduplicated
    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveValue('AAPL, CVX, GOOGL, MSFT, XOM');
    });
  });

  it('should clear list association when symbols are modified', async () => {
    // Arrange
    const onAnalyze = vi.fn();
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

    // Select a list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown before checking textarea
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
    });

    // Modify symbols
    const textarea = screen.getByRole('textbox');
    await user.clear(textarea);
    await user.type(textarea, 'NVDA, AMD');

    // Wait for debounce to clear selection (300ms)
    await new Promise(resolve => setTimeout(resolve, 350));

    // Analyze should pass null for sourceLists
    await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

    await waitFor(() => {
      expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD'], null);
    });
  });

  it('should show error message when list fetch fails', () => {
    // Arrange
    vi.mocked(useStockListsModule.useStockLists).mockReturnValue({
      lists: [],
      isLoading: false,
      error: 'Failed to fetch',
      createList: vi.fn(),
      updateList: vi.fn(),
      deleteList: vi.fn(),
      refetch: vi.fn(),
    });

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    // Assert
    expect(screen.getByText('Failed to load stock lists')).toBeInTheDocument();
  });

  it('should render component title', () => {
    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    // Assert - The component now has a label and button with "Analyze Symbols" text
    expect(screen.getByText('Enter Symbols')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Analyze Symbols' })).toBeInTheDocument();
  });

  it('should disable textarea and button when analyzing', () => {
    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={true} {...defaultProps} />);

    // Assert
    expect(screen.getByRole('textbox')).toBeDisabled();
    // When analyzing, button text becomes "Analyzing..."
    expect(screen.getByRole('button', { name: /Analyzing.../ })).toBeDisabled();
  });

  it('should show symbol count when symbols are entered', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);
    await user.type(screen.getByRole('textbox'), 'AAPL, MSFT');

    // Assert - Symbol count is now shown as inline text "2 symbols entered"
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText(/symbols entered/)).toBeInTheDocument();
    });
  });

  it('should show helper text based on list selection', async () => {
    // Arrange
    const user = userEvent.setup();

    // Act
    render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

    // Initially shows example text (when no symbols entered)
    expect(screen.getByText('Example: AAPL, MSFT, TSLA, NVDA, AMD')).toBeInTheDocument();

    // Select a list
    await user.click(getMultiListSelectorButton());
    await waitFor(() => {
      expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

    // Close dropdown before checking text
    await user.keyboard('{Escape}');

    // Assert - now shows the symbol count instead (since symbols are populated)
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText(/symbols entered/)).toBeInTheDocument();
    });
  });

  describe('symbol modification detection', () => {
    it('should pass sourceLists when symbols are unmodified', async () => {
      // Arrange
      const onAnalyze = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Wait for textarea to be populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Click analyze without modifying symbols
      await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

      // Assert - sourceLists should be passed since symbols are unmodified
      await waitFor(() => {
        expect(onAnalyze).toHaveBeenCalledWith(
          ['AAPL', 'GOOGL', 'MSFT'],
          [{ id: 1, name: 'Tech Watchlist' }]
        );
      });
    });

    it('should pass null for sourceLists when symbol is added', async () => {
      // Arrange
      const onAnalyze = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Wait for textarea to be populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Add a symbol to the textarea
      const textarea = screen.getByRole('textbox');
      await user.clear(textarea);
      await user.type(textarea, 'AAPL, GOOGL, MSFT, NVDA');

      // Click analyze
      await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

      // Assert - sourceLists should be null since symbols were modified
      await waitFor(() => {
        expect(onAnalyze).toHaveBeenCalledWith(
          ['AAPL', 'GOOGL', 'MSFT', 'NVDA'],
          null
        );
      });
    });

    it('should pass null for sourceLists when symbol is removed', async () => {
      // Arrange
      const onAnalyze = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Wait for textarea to be populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Remove a symbol from the textarea
      const textarea = screen.getByRole('textbox');
      await user.clear(textarea);
      await user.type(textarea, 'AAPL, MSFT');

      // Click analyze
      await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

      // Assert - sourceLists should be null since symbols were modified
      await waitFor(() => {
        expect(onAnalyze).toHaveBeenCalledWith(
          ['AAPL', 'MSFT'],
          null
        );
      });
    });

    it('should pass sourceLists when symbols are same but in different order', async () => {
      // Arrange
      const onAnalyze = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Wait for textarea to be populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Reorder symbols in the textarea (set equality check should pass)
      const textarea = screen.getByRole('textbox');
      await user.clear(textarea);
      await user.type(textarea, 'MSFT, AAPL, GOOGL');

      // Click analyze
      await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

      // Assert - sourceLists should be passed since symbols are the same (order doesn't matter)
      await waitFor(() => {
        expect(onAnalyze).toHaveBeenCalledWith(
          ['MSFT', 'AAPL', 'GOOGL'],
          [{ id: 1, name: 'Tech Watchlist' }]
        );
      });
    });

    it('should handle case-insensitive comparison', async () => {
      // Arrange
      const onAnalyze = vi.fn();
      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={onAnalyze} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Wait for textarea to be populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Type same symbols in lowercase
      const textarea = screen.getByRole('textbox');
      await user.clear(textarea);
      await user.type(textarea, 'aapl, googl, msft');

      // Click analyze
      await user.click(screen.getByRole('button', { name: 'Analyze Symbols' }));

      // Assert - sourceLists should be passed since case-insensitive comparison should match
      // Note: parseSymbols() converts to uppercase, so symbols will be uppercase
      await waitFor(() => {
        expect(onAnalyze).toHaveBeenCalledWith(
          ['AAPL', 'GOOGL', 'MSFT'],
          [{ id: 1, name: 'Tech Watchlist' }]
        );
      });
    });
  });

  describe('500 symbol limit', () => {
    it('should show warning when near 500 symbol limit', async () => {
      // Arrange
      const user = userEvent.setup();
      const largeSymbolList = Array.from({ length: 460 }, (_, i) => `SYM${i}`).join(', ');

      // Act
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      await user.click(textarea);
      await user.paste(largeSymbolList);

      // Assert - should show yellow/warning color badge
      await waitFor(() => {
        const badge = screen.getByLabelText(/460 of 500 symbols/i);
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveClass('border-[#fbbf24]');
      });
    });

    it('should show error when over 500 symbol limit', async () => {
      // Arrange
      const user = userEvent.setup();
      const largeSymbolList = Array.from({ length: 510 }, (_, i) => `SYM${i}`).join(', ');

      // Act
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      await user.click(textarea);
      await user.paste(largeSymbolList);

      // Assert
      await waitFor(() => {
        expect(screen.getByText(/Max 500 symbols allowed/)).toBeInTheDocument();
        const badge = screen.getByLabelText(/510 of 500 symbols/i);
        expect(badge).toHaveClass('border-destructive');
      });
    });

    it('should disable analyze button when over 500 symbols', async () => {
      // Arrange
      const user = userEvent.setup();
      const largeSymbolList = Array.from({ length: 510 }, (_, i) => `SYM${i}`).join(', ');

      // Act
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);
      const textarea = screen.getByRole('textbox');
      await user.click(textarea);
      await user.paste(largeSymbolList);

      // Assert
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Analyze Symbols' })).toBeDisabled();
      });
    });
  });

  describe('symbol deduplication', () => {
    it('should deduplicate symbols when combining multiple lists', async () => {
      // Arrange - Create lists with overlapping symbols
      const overlappingLists = [
        { id: 1, name: 'List 1', symbols: ['AAPL', 'MSFT', 'GOOGL'], symbol_count: 3 },
        { id: 2, name: 'List 2', symbols: ['MSFT', 'TSLA', 'NVDA'], symbol_count: 3 },
      ];
      vi.mocked(useStockListsModule.useStockLists).mockReturnValue({
        lists: overlappingLists,
        isLoading: false,
        error: null,
        createList: vi.fn(),
        updateList: vi.fn(),
        deleteList: vi.fn(),
        refetch: vi.fn(),
      });

      const user = userEvent.setup();

      // Act
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

      // Select first list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /List 1/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /List 1/i }));

      // Close dropdown before reopening
      await user.keyboard('{Escape}');

      // Reopen and select second list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /List 2/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /List 2/i }));

      // Close dropdown
      await user.keyboard('{Escape}');

      // Assert - MSFT should appear only once, total 5 unique symbols
      await waitFor(() => {
        const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
        const symbols = textarea.value.split(', ');
        expect(symbols).toHaveLength(5);
        expect(symbols).toContain('AAPL');
        expect(symbols).toContain('GOOGL');
        expect(symbols).toContain('MSFT');
        expect(symbols).toContain('NVDA');
        expect(symbols).toContain('TSLA');
      });
    });
  });

  describe('Clear symbols when all lists unselected', () => {
    it('should clear symbols when all lists are unselected via clear all button', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Verify symbols populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Clear all lists (reopen dropdown, use getByText like MultiListSelector tests)
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByText('Clear all')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Clear all'));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Assert: symbols should be cleared
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('');
      });
    });

    it('should clear symbols when last list is deselected', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Verify symbols populated
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('AAPL, GOOGL, MSFT');
      });

      // Deselect the same list (uncheck it)
      await user.click(getMultiListSelectorButton());
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown before checking textarea
      await user.keyboard('{Escape}');

      // Assert: symbols should be cleared
      await waitFor(() => {
        expect(screen.getByRole('textbox')).toHaveValue('');
      });
    });

    it('should disable analyze button when symbols are cleared', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<Live20Input onAnalyze={vi.fn()} isAnalyzing={false} {...defaultProps} />);

      // Select a list
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i })).toBeInTheDocument();
      });
      await user.click(screen.getByRole('menuitemcheckbox', { name: /Tech Watchlist/i }));

      // Close dropdown and verify analyze button enabled
      await user.keyboard('{Escape}');
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Analyze Symbols/i })).toBeEnabled();
      });

      // Clear all lists (reopen dropdown)
      await user.click(getMultiListSelectorButton());
      await waitFor(() => {
        expect(screen.getByText('Clear all')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Clear all'));

      // Close dropdown before checking button
      await user.keyboard('{Escape}');

      // Assert: analyze button should be disabled
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Analyze Symbols/i })).toBeDisabled();
      });
    });
  });
});
