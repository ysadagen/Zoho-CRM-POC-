import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { EffortQuadrant } from '@/types/enums';
import type { EffortEfficiency } from '@/types/api.types';

import { QuadrantScatter } from './QuadrantScatter';

const REP: EffortEfficiency = {
  rep_user_id: 'u-1',
  rep_email: 'ravi@adagen.in',
  period_start: '2026-05-01',
  period_end: '2026-05-31',
  activity_counts: { visits: 10, meetings: 4, follow_ups: 6, calls: 12, hours_logged: 38 },
  effort_raw: 70,
  effort_score: 80,
  efficiency_components: {
    stage_change_rate: 70,
    won_rate: 65,
    revenue_efficiency: 72,
    time_to_close: 55,
    lead_score_utilization: 60,
  },
  efficiency_score: 75,
  efficiency_band: 'High',
  quadrant: EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY,
};

const REP_HI: EffortEfficiency = {
  ...REP,
  rep_user_id: 'u-hi',
  effort_score: 100,
  efficiency_score: 100,
  quadrant: EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY,
};
const REP_LO: EffortEfficiency = {
  ...REP,
  rep_user_id: 'u-lo',
  effort_score: 0,
  efficiency_score: 0,
  quadrant: EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY,
};

describe('QuadrantScatter', () => {
  it('positions reps relative to the data range with padding', () => {
    render(<QuadrantScatter reps={[REP_HI, REP_LO]} onSelect={vi.fn()} />);
    // viewRange([0, 100]) = [-30, 130] (30% unclamped padding).
    // min always maps to 18.75% and max to 81.25% — always away from the chart edge.
    expect(screen.getByTestId('qs-point-u-hi')).toHaveStyle({ left: '81.25%', bottom: '81.25%' });
    expect(screen.getByTestId('qs-point-u-lo')).toHaveStyle({ left: '18.75%', bottom: '18.75%' });
  });

  it('renders the rep username as the dot label', () => {
    render(<QuadrantScatter reps={[REP]} onSelect={vi.fn()} />);
    // Label shows username (part before @) to avoid overflow in the chart
    expect(screen.getByTestId('qs-point-u-1')).toHaveTextContent('ravi');
  });

  it('reports the selected rep on click', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<QuadrantScatter reps={[REP]} onSelect={onSelect} />);
    await user.click(screen.getByTestId('qs-point-u-1'));
    expect(onSelect).toHaveBeenCalledWith(REP);
  });
});
