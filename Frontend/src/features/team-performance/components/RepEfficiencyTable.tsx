import { useState } from 'react';

import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Skeleton } from '@/components/ui/Skeleton';
import type { EffortEfficiency } from '@/types/api.types';
import { EffortQuadrant } from '@/types/enums';

const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];
const COL_COUNT = 9;

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

const QUADRANT_COLOR: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'var(--success)',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'var(--accent-2)',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'var(--info)',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'var(--danger)',
};

type SortCol = 'effort_score' | 'efficiency_score' | 'won_rate' | 'revenue_efficiency' | 'time_to_close';

function getValue(rep: EffortEfficiency, col: SortCol): number {
  if (col === 'effort_score') return rep.effort_score;
  if (col === 'efficiency_score') return rep.efficiency_score;
  return rep.efficiency_components[col];
}

function shortName(email: string): string {
  return email.split('@')[0] ?? email;
}

interface SortHeaderProps {
  col: SortCol;
  label: string;
  sort: { col: SortCol; dir: 'asc' | 'desc' };
  onSort: (col: SortCol) => void;
}

function SortHeader({ col, label, sort, onSort }: SortHeaderProps): JSX.Element {
  const active = sort.col === col;
  const indicator = active ? (sort.dir === 'desc' ? ' ↓' : ' ↑') : ' ↕';
  return (
    <th className="right sortable" onClick={() => onSort(col)} style={{ cursor: 'pointer', userSelect: 'none' }}>
      {label}
      <span style={{ opacity: active ? 1 : 0.35, fontSize: 10 }}>{indicator}</span>
    </th>
  );
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
  const [sort, setSort] = useState<{ col: SortCol; dir: 'asc' | 'desc' }>({
    col: 'effort_score',
    dir: 'desc',
  });

  function handleSort(col: SortCol): void {
    setSort((prev) =>
      prev.col === col ? { col, dir: prev.dir === 'desc' ? 'asc' : 'desc' } : { col, dir: 'desc' },
    );
  }

  const sorted = [...reps].sort((a, b) => {
    const diff = getValue(a, sort.col) - getValue(b, sort.col);
    return sort.dir === 'desc' ? -diff : diff;
  });

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Rep</th>
            <SortHeader col="effort_score" label="Effort" sort={sort} onSort={handleSort} />
            <SortHeader col="efficiency_score" label="Efficiency" sort={sort} onSort={handleSort} />
            <th>Quadrant</th>
            <SortHeader col="won_rate" label="Won %" sort={sort} onSort={handleSort} />
            <SortHeader col="revenue_efficiency" label="Revenue eff" sort={sort} onSort={handleSort} />
            <SortHeader col="time_to_close" label="Time to close" sort={sort} onSort={handleSort} />
            <th className="right">Stage chg</th>
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
          ) : sorted.length === 0 ? (
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
            sorted.map((rep) => {
              const c = rep.efficiency_components;
              return (
                <tr
                  key={rep.rep_user_id}
                  className="row-click"
                  aria-selected={rep.rep_user_id === selectedId}
                  onClick={() => onSelect(rep)}
                  style={{ borderLeft: `3px solid ${QUADRANT_COLOR[rep.quadrant]}` }}
                >
                  <td>
                    <button
                      type="button"
                      className="tbl-link"
                      title={rep.rep_email}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(rep);
                      }}
                    >
                      {shortName(rep.rep_email)}
                    </button>
                    <div className="sub" style={{ fontSize: 11 }}>
                      {rep.rep_email}
                    </div>
                  </td>
                  <td className="right">
                    <div className="tp-score-cell">
                      <ProgressBar value={rep.effort_score} className="tp-bar" />
                      <span>{Math.round(rep.effort_score)}</span>
                    </div>
                  </td>
                  <td className="right">
                    <div className="tp-score-cell">
                      <ProgressBar value={rep.efficiency_score} className="tp-bar" />
                      <span>{Math.round(rep.efficiency_score)}</span>
                    </div>
                  </td>
                  <td>
                    <Badge variant={QUADRANT_VARIANT[rep.quadrant]} dot>
                      {QUADRANT_LABEL[rep.quadrant]}
                    </Badge>
                  </td>
                  <td className="right muted">{c.won_rate.toFixed(0)}</td>
                  <td className="right muted">{c.revenue_efficiency.toFixed(0)}</td>
                  <td className="right muted">{c.time_to_close.toFixed(0)}</td>
                  <td className="right muted">{c.stage_change_rate.toFixed(0)}</td>
                  <td className="right muted">{c.lead_score_utilization.toFixed(0)}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
