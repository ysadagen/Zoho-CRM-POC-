import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Badge } from './Badge';

describe('Badge', () => {
  it('applies the variant class and renders its label', () => {
    render(
      <Badge variant="success" dot>
        Synced
      </Badge>,
    );
    const el = screen.getByText('Synced');
    expect(el).toHaveClass('badge', 'bd-success');
    expect(el.querySelector('.dot')).not.toBeNull();
  });

  it('omits the dot when not requested', () => {
    render(<Badge variant="danger">Failed</Badge>);
    expect(screen.getByText('Failed').querySelector('.dot')).toBeNull();
  });
});
