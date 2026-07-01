import { Drawer } from '@/components/ui/Drawer';
import type { EffortEfficiency } from '@/types/api.types';
import { EffortQuadrant } from '@/types/enums';

const QUADRANT_COLOR: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'var(--success)',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'var(--accent-2)',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'var(--info)',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'var(--danger)',
};

export interface RepGroupPickerProps {
  reps: EffortEfficiency[];
  onSelect: (rep: EffortEfficiency) => void;
  onClose: () => void;
}

/** Drawer shown when multiple reps share the same dot — lets the user pick one to view details. */
export function RepGroupPicker({ reps, onSelect, onClose }: RepGroupPickerProps): JSX.Element {
  return (
    <Drawer open onClose={onClose} title={`${reps.length} reps at this position`}>
      <p className="sub" style={{ marginBottom: 16 }}>
        These reps share the same scores. Select one to view details.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {reps.map((rep) => (
          <button
            key={rep.rep_user_id}
            type="button"
            className="rep-pick-row"
            onClick={() => onSelect(rep)}
          >
            <span
              className="rep-pick-dot"
              style={{ background: QUADRANT_COLOR[rep.quadrant] }}
              aria-hidden
            />
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontWeight: 500 }}>{rep.rep_email.split('@')[0] ?? rep.rep_email}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {rep.rep_email}
              </div>
            </div>
          </button>
        ))}
      </div>
    </Drawer>
  );
}
