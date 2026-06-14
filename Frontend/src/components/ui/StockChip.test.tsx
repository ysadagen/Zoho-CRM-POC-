import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StockChip } from './StockChip';

describe('StockChip', () => {
  it('renders the variant class and label', () => {
    render(<StockChip variant="short">short by 2</StockChip>);
    const chip = screen.getByText('short by 2');
    expect(chip).toHaveClass('stock-chip', 'short');
  });
});
