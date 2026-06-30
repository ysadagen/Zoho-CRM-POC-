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

function viewRange(values: number[]): [number, number] {
  if (values.length === 0) return [0, 100];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  if (lo === hi) {
    return [lo - 20, hi + 20];
  }
  const pad = (hi - lo) * 0.3;
  return [lo - pad, hi + pad];
}

function toPct(v: number, lo: number, hi: number): number {
  return hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100;
}

export interface QuadrantScatterProps {
  reps: EffortEfficiency[];
  onSelect: (rep: EffortEfficiency) => void;
}

/** Effort (x, 0–100) × efficiency (y, 0–100) scatter, split at 60/60. */
export function QuadrantScatter({ reps, onSelect }: QuadrantScatterProps): JSX.Element {
  const effortVals = reps.map((r) => r.effort_score);
  const effVals = reps.map((r) => r.efficiency_score);

  const [xLo, xHi] = viewRange(effortVals);
  const [yLo, yHi] = viewRange(effVals);

  const threshXPct = toPct(THRESHOLD, xLo, xHi);
  const threshYPct = toPct(THRESHOLD, yLo, yHi);
  const showVline = threshXPct > 2 && threshXPct < 98;
  const showHline = threshYPct > 2 && threshYPct < 98;

  const xMin = effortVals.length ? Math.round(Math.min(...effortVals)) : 0;
  const xMax = effortVals.length ? Math.round(Math.max(...effortVals)) : 100;
  const yMin = effVals.length ? Math.round(Math.min(...effVals)) : 0;
  const yMax = effVals.length ? Math.round(Math.max(...effVals)) : 100;

  return (
    <div className="qs-wrap">
      {/* Y-axis: hi tick → rotated label → lo tick, spanning plot height */}
      <div className="qs-yaxis" aria-hidden>
        <span className="qs-tick">{yMax}</span>
        <span className="qs-alabel-y">Efficiency →</span>
        <span className="qs-tick">{yMin}</span>
      </div>

      {/* Plot */}
      <div className="qs-plot" role="group" aria-label="Effort vs efficiency scatter">
        {/* Quadrant corner labels */}
        <span className="qs-quad" style={{ top: 6, left: 8 }}>
          Low effort{'\n'}High efficiency
        </span>
        <span className="qs-quad" style={{ top: 6, right: 8, textAlign: 'right' }}>
          High effort{'\n'}High efficiency
        </span>
        <span className="qs-quad" style={{ bottom: 6, left: 8 }}>
          Low effort{'\n'}Low efficiency
        </span>
        <span className="qs-quad" style={{ bottom: 6, right: 8, textAlign: 'right' }}>
          High effort{'\n'}Low efficiency
        </span>

        {/* Threshold divider lines */}
        {showVline && <div className="qs-vline" style={{ left: `${threshXPct}%` }} aria-hidden />}
        {showHline && <div className="qs-hline" style={{ bottom: `${threshYPct}%` }} aria-hidden />}

        {/* Rep dots */}
        {reps.map((rep) => {
          const x = toPct(clamp(rep.effort_score), xLo, xHi);
          const y = toPct(clamp(rep.efficiency_score), yLo, yHi);
          const label = rep.rep_email.split('@')[0];
          return (
            <button
              key={rep.rep_user_id}
              type="button"
              className="qs-point"
              style={{ left: `${x}%`, bottom: `${y}%` }}
              data-testid={`qs-point-${rep.rep_user_id}`}
              aria-label={`${rep.rep_email}: effort ${Math.round(rep.effort_score)}, efficiency ${Math.round(rep.efficiency_score)}`}
              onClick={() => onSelect(rep)}
            >
              <span
                className="qs-dot"
                style={{ background: QUADRANT_COLOR[rep.quadrant] }}
                aria-hidden
              />
              <span className="qs-label">{label}</span>
            </button>
          );
        })}
      </div>

      {/* X-axis: empty y-axis spacer | range min + label + range max */}
      <div aria-hidden />
      <div className="qs-xaxis" aria-hidden>
        <span className="qs-tick">{xMin}</span>
        <span className="qs-alabel-x">Effort →</span>
        <span className="qs-tick">{xMax}</span>
      </div>
    </div>
  );
}
