import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('renders the shimmer class and applies sizing', () => {
    const { container } = render(<Skeleton width="60%" height={14} className="x" />);
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveClass('skeleton', 'x');
    expect(el).toHaveAttribute('aria-hidden', 'true');
    expect(el.style.width).toBe('60%');
    expect(el.style.height).toBe('14px');
  });

  it('omits sizing when not provided', () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el.style.width).toBe('');
    expect(el.style.height).toBe('');
  });
});
