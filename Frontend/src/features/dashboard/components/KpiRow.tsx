import { KpiCard } from '@/components/ui/KpiCard';
import { Skeleton } from '@/components/ui/Skeleton';

import { buildKpis } from '../dashboard.transform';
import { useDashboardItems, useDraftPoCount, useDraftSoCount } from '../hooks/useDashboard';
import { LoadError } from './LoadError';

const SKELETON_KEYS = ['a', 'b', 'c', 'd', 'e'];

export function KpiRow(): JSX.Element {
  const items = useDashboardItems();
  const poCount = useDraftPoCount();
  const soCount = useDraftSoCount();

  const error = items.error ?? poCount.error ?? soCount.error;
  const retry = (): void => {
    void items.refetch();
    void poCount.refetch();
    void soCount.refetch();
  };

  if (error) {
    return (
      <div className="card mb-16">
        <LoadError error={error} title="Couldn't load the summary" onRetry={retry} />
      </div>
    );
  }

  if (items.data === undefined || poCount.data === undefined || soCount.data === undefined) {
    return (
      <div className="kpi-row mb-16">
        {SKELETON_KEYS.map((key) => (
          <div className="kpi" key={key}>
            <Skeleton width={34} height={34} />
            <Skeleton width="70%" height={12} className="mt-8" />
            <Skeleton width="50%" height={24} className="mt-8" />
          </div>
        ))}
      </div>
    );
  }

  const kpis = buildKpis({
    items: items.data,
    draftPoCount: poCount.data,
    draftSoCount: soCount.data,
  });

  return (
    <div className="kpi-row mb-16">
      {kpis.map((kpi) => (
        <KpiCard key={kpi.label} {...kpi} />
      ))}
    </div>
  );
}
