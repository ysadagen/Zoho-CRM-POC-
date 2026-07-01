import { Drawer } from '@/components/ui/Drawer';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { EffortEfficiency } from '@/types/api.types';

export interface RepDetailProps {
  rep: EffortEfficiency;
  onClose: () => void;
}

function shortName(email: string): string {
  return email.split('@')[0] ?? email;
}

/** Slide-in drill-down for one rep: activity counts + efficiency sub-scores. */
export function RepDetail({ rep, onClose }: RepDetailProps): JSX.Element {
  const a = rep.activity_counts;
  const c = rep.efficiency_components;

  const activityRows = [
    { label: 'Visits', value: a.visits },
    { label: 'Meetings', value: a.meetings },
    { label: 'Follow-ups', value: a.follow_ups },
    { label: 'Calls', value: a.calls },
    { label: 'Hours logged', value: a.hours_logged },
  ];

  const componentRows = [
    { label: 'Stage change rate', value: c.stage_change_rate },
    { label: 'Won rate', value: c.won_rate },
    { label: 'Revenue efficiency', value: c.revenue_efficiency },
    { label: 'Time to close', value: c.time_to_close },
    { label: 'Lead score utilization', value: c.lead_score_utilization },
  ];

  return (
    <Drawer open onClose={onClose} title={shortName(rep.rep_email)}>
      <div className="sub" style={{ marginBottom: 20 }}>
        {rep.rep_email}
        <br />
        Effort {rep.effort_score.toFixed(0)} · Efficiency {rep.efficiency_score.toFixed(0)} ·{' '}
        {rep.efficiency_band}
      </div>

      <div style={{ marginBottom: 28 }}>
        <div className="sub" style={{ marginBottom: 10, fontWeight: 600 }}>
          Activity counts
        </div>
        {activityRows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between"
            style={{ marginBottom: 6 }}
          >
            <span className="muted">{row.label}</span>
            <span>{row.value}</span>
          </div>
        ))}
      </div>

      <div>
        <div className="sub" style={{ marginBottom: 10, fontWeight: 600 }}>
          Efficiency components
        </div>
        {componentRows.map((row) => (
          <div key={row.label} style={{ marginBottom: 14 }}>
            <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
              <span className="muted">{row.label}</span>
              <span>{row.value.toFixed(0)}</span>
            </div>
            <ProgressBar value={row.value} />
          </div>
        ))}
      </div>
    </Drawer>
  );
}
