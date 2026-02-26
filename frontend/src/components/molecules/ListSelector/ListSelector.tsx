import { List } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { StockList } from '@/services/stockListService';

/**
 * Props for the ListSelector component
 */
interface ListSelectorProps {
  /** Array of available stock lists */
  lists: StockList[];
  /** Currently selected list ID, or null if no list is selected */
  selectedListId: number | null;
  /** Callback fired when a list is selected or cleared */
  onSelect: (listId: number | null) => void;
  /** Whether the lists are currently loading */
  isLoading?: boolean;
}

/**
 * Value used for the "None" option to clear list selection.
 * Using a special string since Radix Select doesn't support null values directly.
 */
const NONE_VALUE = '__none__';

/**
 * ListSelector Component
 *
 * A dropdown component for selecting a stock list from available lists.
 * Includes a "None" option to clear the selection.
 *
 * @example
 * ```tsx
 * <ListSelector
 *   lists={lists}
 *   selectedListId={selectedListId}
 *   onSelect={setSelectedListId}
 *   isLoading={isLoading}
 * />
 * ```
 */
export const ListSelector = ({
  lists,
  selectedListId,
  onSelect,
  isLoading = false,
}: ListSelectorProps) => {
  /**
   * Handle select value change.
   * Converts the special NONE_VALUE back to null.
   */
  const handleValueChange = (value: string) => {
    if (value === NONE_VALUE) {
      onSelect(null);
    } else {
      onSelect(Number(value));
    }
  };

  // Convert selectedListId to string for Radix Select, or NONE_VALUE if null
  const selectValue = selectedListId !== null ? String(selectedListId) : NONE_VALUE;

  return (
    <Select value={selectValue} onValueChange={handleValueChange} disabled={isLoading}>
      <SelectTrigger
        className="h-12 bg-background border-input focus:ring-2 focus:ring-primary"
        aria-label="Select a stock list"
      >
        <div className="flex items-center gap-2">
          <List className="h-4 w-4 text-muted-foreground" />
          <SelectValue placeholder={isLoading ? 'Loading lists...' : 'Select a list'} />
        </div>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE_VALUE}>None</SelectItem>
        {lists.map((list) => (
          <SelectItem key={list.id} value={String(list.id)}>
            {list.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
