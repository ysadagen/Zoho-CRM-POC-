import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { ProgressBar } from './ProgressBar';

describe('ProgressBar', () => {
  it('renders the tone class and a data-driven width', () => {
    const { container } = render(<ProgressBar value={40} tone="danger" />);
    expect(container.querySelector('.bar')).toHaveClass('bar', 'danger');
    expect(container.querySelector('.fill')).toHaveStyle({ width: '40%' });
  });

  it('clamps the width to 0–100%', () => {
    const { container } = render(<ProgressBar value={150} />);
    expect(container.querySelector('.fill')).toHaveStyle({ width: '100%' });
  });

  it('applies a fill override colour when provided', () => {
    const { container } = render(<ProgressBar value={85} fillVar="var(--accent)" />);
    expect(container.querySelector('.fill')).toHaveStyle({ background: 'var(--accent)' });
  });
});
