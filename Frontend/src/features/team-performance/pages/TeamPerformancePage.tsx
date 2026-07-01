import { useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { KpiCard } from '@/components/ui/KpiCard';
import { Segmented } from '@/components/ui/Segmented';
import type { EffortEfficiency } from '@/types/api.types';

import { QuadrantScatter } from '../components/QuadrantScatter';
import { RepDetail } from '../components/RepDetail';
import { RepEfficiencyTable } from '../components/RepEfficiencyTable';
import { RepGroupPicker } from '../components/RepGroupPicker';
import { useEffortEfficiency } from '../hooks/useTeamPerformance';

type PeriodDays = '30' | '60' | '90';

const PERIOD_OPTIONS: Array<{ value: PeriodDays; label: string }> = [
  { value: '30', label: '30D' },
  { value: '60', label: '60D' },
  { value: '90', label: '90D' },
];

function toDates(days: PeriodDays): { period_start: string; period_end: string } {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - Number(days));
  return {
    period_start: start.toISOString().slice(0, 10),
    period_end: end.toISOString().slice(0, 10),
  };
}

function avg(nums: number[]): number {
  return nums.length ? Math.round(nums.reduce((s, n) => s + n, 0) / nums.length) : 0;
}

export function TeamPerformancePage(): JSX.Element {
  const [period, setPeriod] = useState<PeriodDays>('90');

  // selectedGroup: the cluster of reps sharing one dot (may be 1 or many)
  const [selectedGroup, setSelectedGroup] = useState<EffortEfficiency[]>([]);
  // selected: the single rep whose RepDetail is open
  const [selected, setSelected] = useState<EffortEfficiency | null>(null);

  const query = useEffortEfficiency(toDates(period));
  const reps = query.data?.items ?? [];

  const avgEffort = avg(reps.map((r) => r.effort_score));
  const avgEfficiency = avg(reps.map((r) => r.efficiency_score));
  const topRep = reps.length
    ? reps.reduce((best, r) =>
        r.effort_score + r.efficiency_score > best.effort_score + best.efficiency_score ? r : best,
      )
    : null;
  const totalActivities = reps.reduce(
    (s, r) =>
      s +
      r.activity_counts.visits +
      r.activity_counts.meetings +
      r.activity_counts.follow_ups +
      r.activity_counts.calls,
    0,
  );

  // Dot click — may carry a group of reps at the same position
  function handleDotClick(group: EffortEfficiency[]): void {
    setSelectedGroup(group);
    setSelected(group.length === 1 ? (group[0] ?? null) : null);
  }

  // Table row click — always a single rep
  function handleRepSelect(rep: EffortEfficiency): void {
    setSelectedGroup([rep]);
    setSelected(rep);
  }

  // Close the picker entirely
  function handleClose(): void {
    setSelectedGroup([]);
    setSelected(null);
  }

  // Close the detail but stay in the picker if the group has multiple reps
  function handleDetailClose(): void {
    if (selectedGroup.length > 1) {
      setSelected(null);
    } else {
      handleClose();
    }
  }

  return (
    <>
      <PageHeader title="Team Performance" sub="Effort vs efficiency: Who's converting" />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <div className="kpi-row kpi-4">
            <KpiCard icon="sync" label="Avg effort" value={String(avgEffort)} />
            <KpiCard icon="check" label="Avg efficiency" value={String(avgEfficiency)} />
            <KpiCard
              icon="user"
              label="Top performer"
              value={topRep ? (topRep.rep_email.split('@')[0] ?? topRep.rep_email) : '—'}
              tone="success"
            />
            <KpiCard icon="clock" label="Total activities" value={String(totalActivities)} />
          </div>

          <Card pad>
            <CardHeader
              title="Effort × efficiency"
              action={
                <Segmented
                  options={PERIOD_OPTIONS}
                  value={period}
                  onChange={setPeriod}
                  ariaLabel="Period"
                />
              }
            />
            <QuadrantScatter reps={reps} onSelect={handleDotClick} />
            <RepEfficiencyTable
              reps={reps}
              loading={query.isPending}
              selectedId={selected?.rep_user_id}
              onSelect={handleRepSelect}
            />
          </Card>

          {/* Group picker: shown when multiple reps share a dot and no one is selected yet */}
          {selectedGroup.length > 1 && !selected && (
            <RepGroupPicker reps={selectedGroup} onSelect={setSelected} onClose={handleClose} />
          )}

          {/* Detail drawer: single rep or after picking from a group */}
          {selected && <RepDetail rep={selected} onClose={handleDetailClose} />}
        </>
      )}
    </>
  );
}
