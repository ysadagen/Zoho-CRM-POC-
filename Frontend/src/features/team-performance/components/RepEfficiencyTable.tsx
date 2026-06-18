import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { EffortQuadrant } from '@/types/enums';
import type { EffortEfficiency } from '@/types/api.types';

const COL_COUNT = 10;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

const QUADRANT_VARIANT: Record<EffortQuadrant, BadgeVariant> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'success',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'warn',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'info',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'danger',
};

const QUADRANT_LABEL: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'High effort · High efficiency',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'High effort · Low efficiency',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'Low effort · High efficiency',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'Low effort · Low efficiency',
};

function score(value: number): string {
  return value.toFixed(0);
}

export interface RepEfficiencyTableProps {
  reps: EffortEfficiency[];
  loading: boolean;
  selectedId?: string;
  onSelect: (rep: EffortEfficiency) => void;
}

export function RepEfficiencyTable({
  reps,
  loading,
  selectedId,
  onSelect,
}: RepEfficiencyTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Rep</th>
            <th className="right">Effort</th>
            <th className="right">Efficiency</th>
            <th>Band</th>
            <th>Quadrant</th>
            <th className="right">Stage chg</th>
            <th className="right">Won</th>
            <th className="right">Revenue eff</th>
            <th className="right">Time to close</th>
            <th className="right">Lead use</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            SKELETON_ROWS.map((key) => (
              <tr key={key}>
                <td colSpan={COL_COUNT}>
                  <Skeleton height={18} />
                </td>
              </tr>
            ))
          ) : reps.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="user"
                  title="No reps in this period"
                  sub="Try a different period range."
                />
              </td>
            </tr>
          ) : (
            reps.map((rep) => {
              const c = rep.efficiency_components;
              return (
                <tr
                  key={rep.rep_user_id}
                  className="row-click"
                  aria-selected={rep.rep_user_id === selectedId}
                  onClick={() => onSelect(rep)}
                >
                  <td>
                    <button
                      type="button"
                      className="tbl-link"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(rep);
                      }}
                    >
                      {rep.rep_email}
                    </button>
                  </td>
                  <td className="right">{score(rep.effort_score)}</td>
                  <td className="right">{score(rep.efficiency_score)}</td>
                  <td className="muted">{rep.efficiency_band}</td>
                  <td>
                    <Badge variant={QUADRANT_VARIANT[rep.quadrant]} dot>
                      {QUADRANT_LABEL[rep.quadrant]}
                    </Badge>
                  </td>
                  <td className="right muted">{score(c.stage_change_rate)}</td>
                  <td className="right muted">{score(c.won_rate)}</td>
                  <td className="right muted">{score(c.revenue_efficiency)}</td>
                  <td className="right muted">{score(c.time_to_close)}</td>
                  <td className="right muted">{score(c.lead_score_utilization)}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
