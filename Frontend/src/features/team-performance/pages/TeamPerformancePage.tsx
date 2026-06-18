import { useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { formatDate } from '@/lib/format';
import type { EffortEfficiency } from '@/types/api.types';

import { QuadrantScatter } from '../components/QuadrantScatter';
import { RepEfficiencyTable } from '../components/RepEfficiencyTable';
import { RepDetail } from '../components/RepDetail';
import { useEffortEfficiency } from '../hooks/useTeamPerformance';

export function TeamPerformancePage(): JSX.Element {
  const query = useEffortEfficiency();
  const [selected, setSelected] = useState<EffortEfficiency | null>(null);

  const reps = query.data?.items ?? [];
  const period =
    query.data &&
    `${formatDate(query.data.period_start)} – ${formatDate(query.data.period_end)}`;

  return (
    <>
      <PageHeader title="Team Performance" sub="Effort vs efficiency — who's converting" />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card pad>
          <CardHeader
            title="Effort × efficiency"
            sub={period ? `Period: ${period}` : 'Loading period…'}
          />
          <QuadrantScatter reps={reps} onSelect={setSelected} />
          <RepEfficiencyTable
            reps={reps}
            loading={query.isPending}
            selectedId={selected?.rep_user_id}
            onSelect={setSelected}
          />
          {selected && <RepDetail rep={selected} onClose={() => setSelected(null)} />}
        </Card>
      )}
    </>
  );
}
