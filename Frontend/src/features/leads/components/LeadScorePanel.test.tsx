import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import type { LeadScore } from '@/types/api.types';

import { LeadScorePanel } from './LeadScorePanel';

const SCORE: LeadScore = {
  lead_id: 'l1',
  config_version: 1,
  computed_at: '2026-06-18T00:00:00Z',
  components: {
    urgency: 70,
    location: 50,
    contribution_margin: 70,
    quantity: 100,
    product_margin: 60,
  },
  total_score: 70,
  classification: 'MEDIUM',
  defaults_applied: [],
};

describe('LeadScorePanel', () => {
  it('renders the total, band, and the five parameter bars', () => {
    render(<LeadScorePanel score={SCORE} />);
    expect(screen.getByText('70.00')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toHaveClass('bd-warn');
    for (const label of ['Urgency', 'Location', 'Contribution margin', 'Quantity', 'Product margin']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('shows a defaults-applied notice naming the fallback parameters', () => {
    render(
      <LeadScorePanel score={{ ...SCORE, defaults_applied: ['urgency', 'product_margin'] }} />,
    );
    expect(screen.getByText(/Defaults applied/)).toHaveTextContent('Urgency');
    expect(screen.getByText(/Defaults applied/)).toHaveTextContent('Product margin');
  });

  it('omits the defaults notice when none were applied', () => {
    render(<LeadScorePanel score={SCORE} />);
    expect(screen.queryByText(/Defaults applied/)).toBeNull();
  });
});
