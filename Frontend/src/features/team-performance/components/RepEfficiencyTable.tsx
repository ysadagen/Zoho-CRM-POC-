import { useState } from 'react';

import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { cx } from '@/lib/cx';
import type { EffortEfficiency } from '@/types/api.types';
import { EffortQuadrant } from '@/types/enums';

const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];
const COL_COUNT = 9;

type SortCol =
  | 'effort_score'
  | 'efficiency_score'
  | 'won_rate'
  | 'revenue_efficiency'
  | 'time_to_close';

type SortDir = 'asc' | 'desc';

function getValue(rep: EffortEfficiency, col: SortCol): number {
  if (col === 'effort_score') return rep.effort_score;
  if (col === 'efficiency_score') return rep.efficiency_score;
  return rep.efficiency_components[col];
}

function shortName(email: string): string {
  return email.split('@')[0] ?? email;
}

function initials(email: string): string {
  const name = email.split('@')[0] ?? email;
  const parts = name.split(/[._-]/);
  const a = parts[0]?.[0] ?? '';
  const b = parts[1]?.[0] ?? name[1] ?? '';
  return (a + b).toUpperCase();
}

// Quadrant → avatar background CSS variable
const QUADRANT_AVATAR: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'var(--success)',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'var(--accent-2)',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'var(--info)',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'var(--tp-low)',
};

// Quadrant → pill modifier class (pairs with .tp-quadrant-pill base)
const QUADRANT_PILL: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'tp-quadrant-pill--hh',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'tp-quadrant-pill--hl',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'tp-quadrant-pill--lh',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'tp-quadrant-pill--ll',
};

const QUADRANT_LABEL: Record<EffortQuadrant, string> = {
  [EffortQuadrant.HIGH_EFFORT_HIGH_EFFICIENCY]: 'High effort · High efficiency',
  [EffortQuadrant.HIGH_EFFORT_LOW_EFFICIENCY]: 'High effort · Low efficiency',
  [EffortQuadrant.LOW_EFFORT_HIGH_EFFICIENCY]: 'Low effort · High efficiency',
  [EffortQuadrant.LOW_EFFORT_LOW_EFFICIENCY]: 'Low effort · Low efficiency',
};

interface SortHeaderProps {
  col: SortCol;
  label: string;
  sort: { col: SortCol; dir: SortDir };
  onSort: (col: SortCol) => void;
  align?: 'left' | 'right';
}

function SortHeader({ col, label, sort, onSort, align = 'left' }: Readonly<SortHeaderProps>): JSX.Element {
  const active = sort.col === col;
  let ariaSort: 'ascending' | 'descending' | 'none' = 'none';
  if (active) ariaSort = sort.dir === 'desc' ? 'descending' : 'ascending';

  return (
    <th
      scope="col"
      className={cx(
        align === 'right' && 'right',
        active && (sort.dir === 'desc' ? 'tp-sort-desc' : 'tp-sort-asc'),
      )}
      aria-sort={ariaSort}
    >
      <button
        type="button"
        className={cx('tp-sort-btn', align === 'right' && 'tp-sort-btn--right')}
        onClick={() => onSort(col)}
      >
        {label}
        <span className="tp-sort-icon" aria-hidden="true">
          <span className="tp-sort-up" />
          <span className="tp-sort-dn" />
        </span>
      </button>
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
}: Readonly<RepEfficiencyTableProps>): JSX.Element {
  const [sort, setSort] = useState<{ col: SortCol; dir: SortDir }>({
    col: 'effort_score',
    dir: 'desc',
  });

  function handleSort(col: SortCol): void {
    setSort((prev) => {
      if (prev.col !== col) return { col, dir: 'desc' };
      const dir: SortDir = prev.dir === 'desc' ? 'asc' : 'desc';
      return { col, dir };
    });
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
            <th scope="col">Rep</th>
            <SortHeader col="effort_score" label="Effort" sort={sort} onSort={handleSort} />
            <SortHeader
              col="efficiency_score"
              label="Efficiency"
              sort={sort}
              onSort={handleSort}
            />
            <th scope="col">Quadrant</th>
            <SortHeader
              col="won_rate"
              label="Won %"
              sort={sort}
              onSort={handleSort}
              align="right"
            />
            <SortHeader
              col="revenue_efficiency"
              label="Revenue eff"
              sort={sort}
              onSort={handleSort}
              align="right"
            />
            <SortHeader
              col="time_to_close"
              label="Time to close"
              sort={sort}
              onSort={handleSort}
              align="right"
            />
            <th scope="col" className="right">
              Stage chg
            </th>
            <th scope="col" className="right">
              Lead use
            </th>
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
              const isIdle = rep.effort_score === 0 && rep.efficiency_score === 0;
              const effortPct = Math.round(rep.effort_score);
              const effPct = Math.round(rep.efficiency_score);

              return (
                <tr
                  key={rep.rep_user_id}
                  className={cx('row-click', isIdle && 'tp-idle')}
                  aria-selected={rep.rep_user_id === selectedId}
                  onClick={() => onSelect(rep)}
                >
                  {/* Rep: avatar initials + name + email */}
                  <td>
                    <div className="tp-rep-cell">
                      <span
                        className="tp-rep-avatar"
                        style={{
                          background: isIdle ? 'var(--ink-4)' : QUADRANT_AVATAR[rep.quadrant],
                        }}
                        aria-hidden="true"
                      >
                        {initials(rep.rep_email)}
                      </span>
                      <div>
                        <div className="tp-rep-name">{shortName(rep.rep_email)}</div>
                        <div className="tp-rep-tag">{rep.rep_email}</div>
                        <div className="tp-rep-tag">{isIdle ? 'no activity' : 'active'}</div>
                      </div>
                    </div>
                  </td>

                  {/* Effort bar */}
                  <td>
                    <div className="tp-bar-cell">
                      <div className="tp-bar-track" role="presentation">
                        <div
                          className={cx(
                            'tp-bar-fill',
                            isIdle ? 'tp-bar-fill--zero' : 'tp-bar-fill--effort',
                          )}
                          style={{ width: `${isIdle ? 2 : effortPct}%` }}
                        />
                      </div>
                      <span className={cx('tp-bar-val', isIdle && 'tp-bar-val--muted')}>
                        {effortPct}
                      </span>
                    </div>
                  </td>

                  {/* Efficiency bar */}
                  <td>
                    <div className="tp-bar-cell">
                      <div className="tp-bar-track" role="presentation">
                        <div
                          className={cx(
                            'tp-bar-fill',
                            isIdle ? 'tp-bar-fill--zero' : 'tp-bar-fill--efficiency',
                          )}
                          style={{ width: `${isIdle ? 2 : effPct}%` }}
                        />
                      </div>
                      <span className={cx('tp-bar-val', isIdle && 'tp-bar-val--muted')}>
                        {effPct}
                      </span>
                    </div>
                  </td>

                  {/* Quadrant pill */}
                  <td>
                    <span
                      className={cx('tp-quadrant-pill', QUADRANT_PILL[rep.quadrant])}
                    >
                      <span className="tp-quadrant-dot" aria-hidden="true" />
                      {QUADRANT_LABEL[rep.quadrant]}
                    </span>
                  </td>

                  {/* Numeric metric columns */}
                  <td className={cx('tp-num', c.won_rate === 0 && 'tp-num--zero')}>
                    {c.won_rate.toFixed(0)}
                    <span className="tp-num-suffix">%</span>
                  </td>
                  <td className={cx('tp-num', c.revenue_efficiency === 0 && 'tp-num--zero')}>
                    {c.revenue_efficiency.toFixed(0)}
                  </td>
                  <td className={cx('tp-num', c.time_to_close === 0 && 'tp-num--zero')}>
                    {c.time_to_close.toFixed(0)}
                  </td>
                  <td className={cx('tp-num', c.stage_change_rate === 0 && 'tp-num--zero')}>
                    {c.stage_change_rate.toFixed(0)}
                  </td>
                  <td className={cx('tp-num', c.lead_score_utilization === 0 && 'tp-num--zero')}>
                    {c.lead_score_utilization.toFixed(0)}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
