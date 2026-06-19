import { useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Segmented } from '@/components/ui/Segmented';
import { HealthClassification } from '@/types/enums';

import { CustomerHealthDrawer } from '../components/CustomerHealthDrawer';
import { CustomerHealthTable } from '../components/CustomerHealthTable';
import { useCustomerHealthList } from '../hooks/useCustomerHealth';

const ALL = 'ALL';
type Filter = typeof ALL | HealthClassification;

const FILTER_OPTIONS: Array<{ value: Filter; label: string }> = [
  { value: ALL, label: 'All' },
  { value: HealthClassification.HEALTHY, label: 'Healthy' },
  { value: HealthClassification.STABLE, label: 'Stable' },
  { value: HealthClassification.AT_RISK, label: 'At Risk' },
  { value: HealthClassification.CRITICAL, label: 'Critical' },
];

export function CustomerHealthPage(): JSX.Element {
  const [filter, setFilter] = useState<Filter>(ALL);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const query = useCustomerHealthList({
    classification: filter === ALL ? undefined : filter,
  });

  return (
    <>
      <PageHeader
        title="Customer Health"
        sub="Who's healthy vs at churn risk — computed live"
      />

      {query.isError && !query.data ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <Card>
          <div className="card-head">
            <Segmented
              ariaLabel="Filter by health classification"
              options={FILTER_OPTIONS}
              value={filter}
              onChange={setFilter}
            />
          </div>
          <CustomerHealthTable
            rows={query.data?.items ?? []}
            loading={query.isPending}
            onSelect={setSelectedId}
          />
        </Card>
      )}

      {selectedId && (
        <CustomerHealthDrawer customerId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  );
}
