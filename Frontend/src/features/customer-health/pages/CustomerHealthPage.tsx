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
const STALE_HOURS = 8;
type Filter = typeof ALL | HealthClassification;

const FILTER_OPTIONS: Array<{ value: Filter; label: string }> = [
  { value: ALL, label: 'All' },
  { value: HealthClassification.HEALTHY, label: 'Healthy' },
  { value: HealthClassification.STABLE, label: 'Stable' },
  { value: HealthClassification.AT_RISK, label: 'At Risk' },
  { value: HealthClassification.CRITICAL, label: 'Critical' },
];

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function isStale(iso: string | null | undefined): boolean {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() > STALE_HOURS * 3_600_000;
}

function ComputingPanel(): JSX.Element {
  return (
    <div className="computing-panel" role="status" aria-label="Computing health scores">
      <div className="compute-ring-wrap">
        <span className="cr cr1" aria-hidden="true" />
        <span className="cr cr2" aria-hidden="true" />
        <span className="cr cr3" aria-hidden="true" />
        <div className="compute-core" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="28"
            height="28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
          </svg>
        </div>
      </div>
      <p className="computing-title">Building your first health report</p>
      <p className="computing-sub">
        Scoring all active customers &mdash; usually takes 15&ndash;30 seconds.
      </p>
    </div>
  );
}

export function CustomerHealthPage(): JSX.Element {
  const [filter, setFilter] = useState<Filter>(ALL);
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<number | false>(false);

  useEffect(() => {
    setPage(0);
  }, [filter]);

  const query = useCustomerHealthList(
    {
      classification: filter === ALL ? undefined : filter,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    },
    { refetchInterval: pollInterval },
  );

  // Start polling when cold-start is detected; stop as soon as scores arrive.
  useEffect(() => {
    if (query.data !== undefined) {
      const coldStart = query.data.total === 0 && query.data.last_computed_at === null;
      setPollInterval(coldStart ? 3_000 : false);
    }
  }, [query.data]);

  const data = query.data;
  const isColdStart =
    !query.isPending &&
    data !== undefined &&
    data.total === 0 &&
    data.last_computed_at === null;
  const isStaleRefresh = !query.isPending && (data?.total ?? 0) > 0 && isStale(data?.last_computed_at);

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const showPager = total > PAGE_SIZE;

  const headerSub = data?.last_computed_at
    ? `Scores as of ${relativeTime(data.last_computed_at)}`
    : 'Scores appear once the Intelligence service has computed them';

  return (
    <>
      <PageHeader title="Customer Health" sub={headerSub} />

      {query.isError && !data ? (
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
            {isStaleRefresh && (
              <span className="ch-refresh-badge" aria-live="polite">
                <span className="pulse-dot" aria-hidden="true" />
                Refreshing
              </span>
            )}
          </div>

          {isColdStart ? (
            <ComputingPanel />
          ) : (
            <CustomerHealthTable
              rows={data?.items ?? []}
              loading={query.isPending}
              onSelect={setSelectedId}
            />
          )}

          {showPager && !isColdStart && (
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
