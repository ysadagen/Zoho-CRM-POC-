import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useDebounce } from './useDebounce';

afterEach(() => vi.useRealTimers());

describe('useDebounce', () => {
  it('returns the latest value only after the delay elapses', () => {
    vi.useFakeTimers();
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 200), {
      initialProps: { v: 'a' },
    });
    expect(result.current).toBe('a');

    rerender({ v: 'b' });
    expect(result.current).toBe('a'); // not yet

    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe('b');
  });
});
