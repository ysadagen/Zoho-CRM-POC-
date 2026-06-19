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

describe('QuadrantScatter', () => {
  it('positions a rep dot by effort (x) and efficiency (y)', () => {
    render(<QuadrantScatter reps={[REP]} onSelect={vi.fn()} />);
    const point = screen.getByTestId('qs-point-u-1');
    expect(point).toHaveStyle({ left: '80%', bottom: '75%' });
    expect(point).toHaveTextContent('ravi@adagen.in');
  });

  it('reports the selected rep on click', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<QuadrantScatter reps={[REP]} onSelect={onSelect} />);
    await user.click(screen.getByTestId('qs-point-u-1'));
    expect(onSelect).toHaveBeenCalledWith(REP);
  });
});
