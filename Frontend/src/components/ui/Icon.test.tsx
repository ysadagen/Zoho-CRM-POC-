import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Icon } from './Icon';

describe('Icon', () => {
  it('renders an SVG, decorative (aria-hidden) by default', () => {
    const { container } = render(<Icon name="home" />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute('aria-hidden', 'true');
  });

  it('becomes a labelled image when given a title', () => {
    render(<Icon name="help" title="Help" />);
    expect(screen.getByRole('img', { name: 'Help' })).toBeInTheDocument();
  });

  it('honours an explicit size', () => {
    const { container } = render(<Icon name="plus" size={14} />);
    expect(container.querySelector('svg')).toHaveAttribute('width', '14');
  });
});
