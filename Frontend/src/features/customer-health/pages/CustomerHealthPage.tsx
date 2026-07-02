import { useEffect, useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { Segmented } from '@/components/ui/Segmented';
import { HealthClassification } from '@/types/enums';

import { CustomerHealthDrawer } from '../components/CustomerHealthDrawer';
import { CustomerHealthTable } from '../components/CustomerHealthTable';
import { useCustomerHealthList } from '../hooks/useCustomerHealth';

const ALL = 'ALL';
const PAGE_SIZE = 25;
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
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Reset to first page whenever the filter changes.
  useEffect(() => {
    setPage(0);
  }, [filter]);

  const query = useCustomerHealthList({
    classification: filter === ALL ? undefined : filter,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const showPager = total > PAGE_SIZE;

  return (
    <>
      <PageHeader
        title="Customer Health"
        sub="Latest snapshot scores — run Recompute to refresh"
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
          {showPager && (
            <div className="card-foot">
              <div className="pager" role="navigation" aria-label="Pagination">
                <button
                  type="button"
                  className="arrow"
                  onClick={() => setPage((p) => p - 1)}
                  disabled={page === 0}
                  aria-label="Previous page"
                >
                  &#8249;
                </button>
                <span className="pg active" aria-current="page">
                  {page + 1}
                </span>
                <span className="pg" aria-label={`of ${totalPages} pages`}>
                  / {totalPages}
                </span>
                <button
                  type="button"
                  className="arrow"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page >= totalPages - 1}
                  aria-label="Next page"
                >
                  &#8250;
                </button>
              </div>
            </div>
          )}
        </Card>
      )}

      {selectedId && (
        <CustomerHealthDrawer customerId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  );
}
