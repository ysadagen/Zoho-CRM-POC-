import { EffortQuadrant } from '@/types/enums';
import type { EffortEfficiency } from '@/types/api.types';

import '../team-performance.css';

/** Quadrant → design-system colour variable (no hard-coded brand colours). */
const QUADRANT_COLOR: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'var(--success)',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'var(--accent-2)',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'var(--info)',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'var(--danger)',
};

const THRESHOLD = 60;

function clamp(value: number): number {
  return Math.max(0, Math.min(100, value));
}

export interface QuadrantScatterProps {
  reps: EffortEfficiency[];
  onSelect: (rep: EffortEfficiency) => void;
}

/** Effort (x, 0–100) × efficiency (y, 0–100) scatter, split at 60/60. */
export function QuadrantScatter({ reps, onSelect }: QuadrantScatterProps): JSX.Element {
  return (
    <div className="qs-grid">
      <div className="qs-axis-y" aria-hidden>
        Efficiency →
      </div>
      <div className="qs-plot" role="group" aria-label="Effort vs efficiency scatter">
        <div className="qs-vline" style={{ left: `${THRESHOLD}%` }} aria-hidden />
        <div className="qs-hline" style={{ bottom: `${THRESHOLD}%` }} aria-hidden />
        {reps.map((rep) => {
          const x = clamp(rep.effort_score);
          const y = clamp(rep.efficiency_score);
          return (
            <button
              key={rep.rep_user_id}
              type="button"
              className="qs-point"
              style={{ left: `${x}%`, bottom: `${y}%` }}
              data-testid={`qs-point-${rep.rep_user_id}`}
              aria-label={`${rep.rep_email}: effort ${x}, efficiency ${y}`}
              onClick={() => onSelect(rep)}
            >
              <span
                className="qs-dot"
                style={{ background: QUADRANT_COLOR[rep.quadrant] }}
                aria-hidden
              />
              <span className="qs-label">{rep.rep_email}</span>
            </button>
          );
        })}
      </div>
      <div />
      <div className="qs-axis-x" aria-hidden>
        Effort →
      </div>
    </div>
  );
}
