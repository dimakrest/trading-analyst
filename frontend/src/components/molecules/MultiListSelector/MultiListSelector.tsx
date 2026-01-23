import { useState } from 'react';
import { List, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import type { StockList } from '@/services/stockListService';

interface MultiListSelectorProps {
  /** Array of available stock lists */
  lists: StockList[];
  /** Currently selected list IDs */
  selectedListIds: number[];
  /** Callback fired when selection changes */
  onSelectionChange: (listIds: number[]) => void;
  /** Total unique symbol count from selected lists */
  uniqueSymbolCount: number;
  /** Maximum allowed symbols */
  maxSymbols?: number;
  /** Whether the lists are currently loading */
  isLoading?: boolean;
  /** Whether the selector is disabled */
  disabled?: boolean;
}

/**
 * MultiListSelector Component
 *
 * A dropdown component for selecting multiple stock lists.
 * Shows real-time symbol count with color-coded limit warnings.
 */
export const MultiListSelector = ({
  lists,
  selectedListIds,
  onSelectionChange,
  uniqueSymbolCount,
  maxSymbols = 500,
  isLoading = false,
  disabled = false,
}: MultiListSelectorProps) => {
  const [open, setOpen] = useState(false);

  const handleToggle = (listId: number, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedListIds, listId]);
    } else {
      onSelectionChange(selectedListIds.filter((id) => id !== listId));
    }
  };

  const handleClearAll = () => {
    onSelectionChange([]);
  };

  const handleSelectAll = () => {
    onSelectionChange(lists.map((list) => list.id));
  };

  const selectedCount = selectedListIds.length;
  const isOverLimit = uniqueSymbolCount > maxSymbols;
  const isNearLimit = uniqueSymbolCount > maxSymbols * 0.9 && !isOverLimit;

  // Determine badge color based on count
  const getBadgeClassName = () => {
    if (isOverLimit) {
      return 'border-destructive text-destructive';
    }
    if (isNearLimit) {
      return 'border-[#fbbf24] bg-[rgba(245,158,11,0.12)] text-[#fbbf24]';
    }
    return 'border-[rgba(167,139,250,0.3)] bg-[rgba(167,139,250,0.12)] text-[#c4b5fd]';
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild disabled={disabled || isLoading}>
        <Button
          variant="outline"
          className="h-12 w-full justify-between bg-background border-input focus:ring-2 focus:ring-primary"
          aria-label={
            selectedCount === 0
              ? 'Select stock lists'
              : `${selectedCount} list${selectedCount === 1 ? '' : 's'} selected with ${uniqueSymbolCount} unique symbol${uniqueSymbolCount === 1 ? '' : 's'}`
          }
        >
          <div className="flex items-center gap-2">
            <List className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">
              {isLoading
                ? 'Loading lists...'
                : selectedCount === 0
                  ? 'Select lists...'
                  : `${selectedCount} list${selectedCount > 1 ? 's' : ''} selected`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {selectedCount > 0 && (
              <Badge variant="outline" className={cn('font-mono text-xs', getBadgeClassName())}>
                {uniqueSymbolCount}/{maxSymbols}
              </Badge>
            )}
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </div>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-[320px]" align="start">
        <DropdownMenuLabel className="flex justify-between items-center">
          <span>Select Lists</span>
          <div className="flex gap-1">
            {selectedCount < lists.length && lists.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleSelectAll}
                className="text-xs h-6 px-2"
              >
                Select all
              </Button>
            )}
            {selectedCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearAll}
                className="text-xs h-6 px-2"
              >
                Clear all
              </Button>
            )}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />

        {lists.length === 0 ? (
          <div className="px-2 py-4 text-sm text-muted-foreground text-center">
            No lists available
          </div>
        ) : (
          lists.map((list) => (
            <DropdownMenuCheckboxItem
              key={list.id}
              checked={selectedListIds.includes(list.id)}
              onCheckedChange={(checked) => handleToggle(list.id, checked)}
              onSelect={(e) => e.preventDefault()}
              aria-label={`${list.name} with ${list.symbol_count} symbols`}
            >
              <div className="flex justify-between items-center w-full">
                <span className="text-sm truncate">{list.name}</span>
                <span className="text-xs text-muted-foreground font-mono ml-2 flex-shrink-0">
                  {list.symbol_count}
                </span>
              </div>
            </DropdownMenuCheckboxItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
