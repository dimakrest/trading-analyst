import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: (symbol: string) => void;
}

export const SearchBar = ({ value, onSearch }: SearchBarProps) => {
  const [inputValue, setInputValue] = useState(value);

  // Sync internal state when external value changes (e.g., from watchlist click)
  useEffect(() => {
    setInputValue(value);
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onSearch(inputValue);
    }
  };

  return (
    <div className="relative">
      <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground pointer-events-none" />
      <Input
        type="text"
        placeholder="Search for stocks e.g. AAPL, TSLA"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        className="pl-12 h-12 text-base font-medium bg-background border-input focus-visible:ring-2 focus-visible:ring-primary"
        aria-label="Stock symbol search"
      />
    </div>
  );
};
