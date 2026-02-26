import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAsync } from './useAsync';

describe('useAsync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial State', () => {
    it('starts with null data, no loading, and no error', () => {
      const asyncFn = vi.fn();
      const { result } = renderHook(() => useAsync(asyncFn));

      expect(result.current.data).toBe(null);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe(null);
    });

    it('uses initialData when provided', () => {
      const asyncFn = vi.fn();
      const { result } = renderHook(() =>
        useAsync(asyncFn, { initialData: 'initial' })
      );

      expect(result.current.data).toBe('initial');
    });
  });

  describe('Execute', () => {
    it('sets loading state during execution', async () => {
      let resolvePromise: (value: string) => void;
      const asyncFn = vi.fn(
        () =>
          new Promise<string>((resolve) => {
            resolvePromise = resolve;
          })
      );

      const { result } = renderHook(() => useAsync(asyncFn));

      expect(result.current.loading).toBe(false);

      act(() => {
        result.current.execute();
      });

      expect(result.current.loading).toBe(true);

      await act(async () => {
        resolvePromise!('result');
      });

      expect(result.current.loading).toBe(false);
    });

    it('updates data on successful execution', async () => {
      const asyncFn = vi.fn().mockResolvedValue('success data');
      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.data).toBe('success data');
      expect(result.current.error).toBe(null);
    });

    it('passes arguments to async function', async () => {
      const asyncFn = vi.fn().mockResolvedValue('result');
      const { result } = renderHook(() =>
        useAsync<string, [string, number]>(asyncFn)
      );

      await act(async () => {
        await result.current.execute('arg1', 42);
      });

      expect(asyncFn).toHaveBeenCalledWith('arg1', 42, expect.any(AbortSignal));
    });

    it('calls onSuccess callback on successful execution', async () => {
      const onSuccess = vi.fn();
      const asyncFn = vi.fn().mockResolvedValue('data');
      const { result } = renderHook(() => useAsync(asyncFn, { onSuccess }));

      await act(async () => {
        await result.current.execute();
      });

      expect(onSuccess).toHaveBeenCalledWith('data');
    });
  });

  describe('Error Handling', () => {
    it('sets error state on Error exception', async () => {
      const asyncFn = vi.fn().mockRejectedValue(new Error('Test error'));
      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.error).toBe('Test error');
      expect(result.current.data).toBe(null);
      expect(result.current.loading).toBe(false);
    });

    it('sets generic error for non-Error exceptions', async () => {
      const asyncFn = vi.fn().mockRejectedValue('string error');
      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.error).toBe('An unexpected error occurred');
    });

    it('calls onError callback on error', async () => {
      const onError = vi.fn();
      const asyncFn = vi.fn().mockRejectedValue(new Error('Test error'));
      const { result } = renderHook(() => useAsync(asyncFn, { onError }));

      await act(async () => {
        await result.current.execute();
      });

      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });

    it('clears error on new execution', async () => {
      const asyncFn = vi
        .fn()
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValueOnce('success');
      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });
      expect(result.current.error).toBe('Error');

      await act(async () => {
        await result.current.execute();
      });
      expect(result.current.error).toBe(null);
      expect(result.current.data).toBe('success');
    });
  });

  describe('Cancellation', () => {
    it('cancels in-progress request', async () => {
      const asyncFn = vi.fn(
        () =>
          new Promise<string>(() => {
            // Never resolves - simulates long-running request
          })
      );

      const { result } = renderHook(() => useAsync(asyncFn));

      act(() => {
        result.current.execute();
      });

      expect(result.current.loading).toBe(true);

      act(() => {
        result.current.cancel();
      });

      expect(result.current.loading).toBe(false);
    });

    it('does not update state for cancelled requests', async () => {
      const abortError = new Error('AbortError');
      abortError.name = 'AbortError';
      const asyncFn = vi.fn().mockRejectedValue(abortError);

      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });

      // Should not set error for AbortError
      expect(result.current.error).toBe(null);
    });

    it('handles CanceledError from axios', async () => {
      const canceledError = new Error('CanceledError');
      canceledError.name = 'CanceledError';
      const asyncFn = vi.fn().mockRejectedValue(canceledError);

      const { result } = renderHook(() => useAsync(asyncFn));

      await act(async () => {
        await result.current.execute();
      });

      // Should not set error for CanceledError
      expect(result.current.error).toBe(null);
    });

    it('cancels previous request when new one starts', async () => {
      let callCount = 0;
      const asyncFn = vi.fn(async () => {
        callCount++;
        await new Promise((resolve) => setTimeout(resolve, 100));
        return `result-${callCount}`;
      });

      const { result } = renderHook(() => useAsync(asyncFn));

      // Start first request
      act(() => {
        result.current.execute();
      });

      // Start second request immediately (should cancel first)
      await act(async () => {
        await result.current.execute();
      });

      // Should have the result from the second call
      expect(result.current.data).toBe('result-2');
    });
  });

  describe('Reset', () => {
    it('resets to initial state', async () => {
      const asyncFn = vi.fn().mockResolvedValue('data');
      const { result } = renderHook(() =>
        useAsync(asyncFn, { initialData: 'initial' })
      );

      await act(async () => {
        await result.current.execute();
      });
      expect(result.current.data).toBe('data');

      act(() => {
        result.current.reset();
      });

      expect(result.current.data).toBe('initial');
      expect(result.current.error).toBe(null);
      expect(result.current.loading).toBe(false);
    });
  });

  describe('SetData', () => {
    it('allows manual data updates', () => {
      const asyncFn = vi.fn();
      const { result } = renderHook(() => useAsync(asyncFn));

      act(() => {
        result.current.setData('manual data');
      });

      expect(result.current.data).toBe('manual data');
    });
  });
});
