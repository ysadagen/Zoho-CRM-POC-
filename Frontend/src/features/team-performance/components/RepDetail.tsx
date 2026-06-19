import { Button } from '@/components/ui/Button';
import type { EffortEfficiency } from '@/types/api.types';

interface Stat {
  label: string;
  value: number;
}

export interface RepDetailProps {
  rep: EffortEfficiency;
  onClose: () => void;
}

/** Drill-down for one rep: raw activity counts + efficiency sub-scores. */
export function RepDetail({ rep, onClose }: RepDetailProps): JSX.Element {
  const a = rep.activity_counts;
  const c = rep.efficiency_components;

  const activity: Stat[] = [
    { label: 'Visits', value: a.visits },
    { label: 'Meetings', value: a.meetings },
    { label: 'Follow-ups', value: a.follow_ups },
    { label: 'Calls', value: a.calls },
    { label: 'Hours logged', value: a.hours_logged },
  ];

  const components: Stat[] = [
    { label: 'Stage change rate', value: c.stage_change_rate },
    { label: 'Won rate', value: c.won_rate },
    { label: 'Revenue efficiency', value: c.revenue_efficiency },
    { label: 'Time to close', value: c.time_to_close },
    { label: 'Lead score utilization', value: c.lead_score_utilization },
  ];

  return (
    <section className="card card-pad" aria-label={`Detail for ${rep.rep_email}`}>
      <div className="card-head">
        <div>
          <h3>{rep.rep_email}</h3>
          <div className="sub">
            Effort {rep.effort_score.toFixed(0)} · Efficiency {rep.efficiency_score.toFixed(0)} ·{' '}
            {rep.efficiency_band}
          </div>
        </div>
        <Button variant="sec" icon="close" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="grid-2">
        <div>
          <div className="sub">Activity counts</div>
          {activity.map((s) => (
            <div key={s.label} className="flex items-center justify-between">
              <span className="muted">{s.label}</span>
              <span>{s.value}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="sub">Efficiency components</div>
          {components.map((s) => (
            <div key={s.label} className="flex items-center justify-between">
              <span className="muted">{s.label}</span>
              <span>{s.value.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
