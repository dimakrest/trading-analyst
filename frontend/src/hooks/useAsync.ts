import { useState, useCallback, useRef } from 'react';

/**
 * State returned by the useAsync hook
 */
export interface AsyncState<T> {
  /** The data returned from the async operation (null if not yet executed or on error) */
  data: T | null;
  /** Whether an async operation is in progress */
  loading: boolean;
  /** Error message if the operation failed (null on success) */
  error: string | null;
}

/**
 * Result object returned by useAsync hook
 */
export interface UseAsyncResult<T, Args extends unknown[]> extends AsyncState<T> {
  /** Execute the async operation with provided arguments */
  execute: (...args: Args) => Promise<T | null>;
  /** Cancel any in-progress async operation */
  cancel: () => void;
  /** Reset state to initial values */
  reset: () => void;
  /** Set data directly (useful for optimistic updates) */
  setData: (data: T | null) => void;
}

/**
 * Options for the useAsync hook
 */
export interface UseAsyncOptions<T> {
  /** Initial data value (default: null) */
  initialData?: T | null;
  /** Callback when operation succeeds */
  onSuccess?: (data: T) => void;
  /** Callback when operation fails */
  onError?: (error: Error) => void;
}

/**
 * Generic hook for managing async operations with loading, error, and cancellation support.
 *
 * Extracts the common state machine pattern used across data-fetching hooks:
 * - loading: boolean state for UI feedback
 * - error: string | null for error display
 * - data: T | null for the operation result
 * - Automatic AbortController management for cancellation
 *
 * @param asyncFn - The async function to execute. Receives an AbortSignal as the last argument.
 * @param options - Optional configuration for initial data and callbacks
 * @returns Object containing state and control functions
 *
 * @example
 * // Basic usage
 * const { data, loading, error, execute } = useAsync(
 *   async (id: number, signal: AbortSignal) => {
 *     const response = await fetch(`/api/items/${id}`, { signal });
 *     return response.json();
 *   }
 * );
 *
 * // Execute the operation
 * await execute(123);
 *
 * @example
 * // With callbacks
 * const { execute, cancel } = useAsync(
 *   async (query: string, signal: AbortSignal) => searchAPI(query, signal),
 *   {
 *     onSuccess: (results) => console.log('Found:', results.length),
 *     onError: (err) => toast.error(err.message),
 *   }
 * );
 */
export function useAsync<T, Args extends unknown[] = []>(
  asyncFn: (...args: [...Args, AbortSignal]) => Promise<T>,
  options: UseAsyncOptions<T> = {}
): UseAsyncResult<T, Args> {
  const { initialData = null, onSuccess, onError } = options;

  const [data, setData] = useState<T | null>(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use ref for abort controller to avoid re-renders and stale closures
  const abortControllerRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    cancel();
    setData(initialData);
    setError(null);
    setLoading(false);
  }, [cancel, initialData]);

  const execute = useCallback(
    async (...args: Args): Promise<T | null> => {
      // Cancel any in-progress request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      setError(null);

      try {
        const result = await asyncFn(...args, controller.signal);

        // Only update state if this request wasn't cancelled
        if (!controller.signal.aborted) {
          setData(result);
          onSuccess?.(result);
        }

        return result;
      } catch (err) {
        // Don't update state for cancelled requests
        if (err instanceof Error) {
          if (err.name === 'AbortError' || err.name === 'CanceledError') {
            return null;
          }
          setError(err.message);
          onError?.(err);
        } else {
          const errorMessage = 'An unexpected error occurred';
          setError(errorMessage);
          onError?.(new Error(errorMessage));
        }
        return null;
      } finally {
        // Only clear loading if this is still the active request
        if (abortControllerRef.current === controller) {
          setLoading(false);
          abortControllerRef.current = null;
        }
      }
    },
    [asyncFn, onSuccess, onError]
  );

  return {
    data,
    loading,
    error,
    execute,
    cancel,
    reset,
    setData,
  };
}
