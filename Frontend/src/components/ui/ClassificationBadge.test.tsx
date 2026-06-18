import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ClassificationBadge } from './ClassificationBadge';

describe('ClassificationBadge', () => {
  it('maps lead bands to the right variant + label', () => {
    render(<ClassificationBadge scale="lead" value="HOT" />);
    const el = screen.getByText('Hot');
    expect(el).toHaveClass('badge', 'bd-danger');
  });

  it('maps every lead band', () => {
    const { rerender } = render(<ClassificationBadge scale="lead" value="MEDIUM" />);
    expect(screen.getByText('Medium')).toHaveClass('bd-warn');
    rerender(<ClassificationBadge scale="lead" value="COLD" />);
    expect(screen.getByText('Cold')).toHaveClass('bd-info');
  });

  it('maps health bands (incl. the At Risk label)', () => {
    const { rerender } = render(<ClassificationBadge scale="health" value="HEALTHY" />);
    expect(screen.getByText('Healthy')).toHaveClass('bd-success');
    rerender(<ClassificationBadge scale="health" value="STABLE" />);
    expect(screen.getByText('Stable')).toHaveClass('bd-info');
    rerender(<ClassificationBadge scale="health" value="AT_RISK" />);
    expect(screen.getByText('At Risk')).toHaveClass('bd-warn');
    rerender(<ClassificationBadge scale="health" value="CRITICAL" />);
    expect(screen.getByText('Critical')).toHaveClass('bd-danger');
  });

  it('disambiguates MEDIUM by scale (priority = info, lead = warn)', () => {
    const { rerender } = render(<ClassificationBadge scale="priority" value="MEDIUM" />);
    expect(screen.getByText('Medium')).toHaveClass('bd-info');
    rerender(<ClassificationBadge scale="priority" value="HIGH" />);
    expect(screen.getByText('High')).toHaveClass('bd-warn');
    rerender(<ClassificationBadge scale="priority" value="LOW" />);
    expect(screen.getByText('Low')).toHaveClass('bd-ink');
  });

  it('renders a status dot when requested', () => {
    render(<ClassificationBadge scale="lead" value="HOT" dot />);
    expect(screen.getByText('Hot').querySelector('.dot')).not.toBeNull();
  });
});
