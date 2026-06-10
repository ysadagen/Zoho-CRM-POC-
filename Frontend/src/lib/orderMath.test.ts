import { describe, it, expect } from 'vitest';

import { estimatedTotal, lineTotal } from './orderMath';

describe('orderMath', () => {
  it('lineTotal multiplies only when both values are present', () => {
    expect(lineTotal('10', '5')).toBe(50);
    expect(lineTotal('10', '')).toBeNull();
    expect(lineTotal('', '5')).toBeNull();
    expect(lineTotal('x', '5')).toBeNull();
  });

  it('estimatedTotal sums priced lines and ignores unpriced ones', () => {
    expect(
      estimatedTotal([
        { quantity: '10', unit_price: '5' },
        { quantity: '3', unit_price: '' },
        { quantity: '2', unit_price: '2.5' },
      ]),
    ).toBe(55);
    expect(estimatedTotal([])).toBe(0);
  });
});
