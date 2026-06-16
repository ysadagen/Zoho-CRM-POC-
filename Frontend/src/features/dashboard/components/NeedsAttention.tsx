import { routes } from '@/app/routes';
import { ButtonLink } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Skeleton } from '@/components/ui/Skeleton';

import { lowStockItems, toLowStockVM } from '../dashboard.transform';
import { useDashboardItems } from '../hooks/useDashboard';
import { LoadError } from './LoadError';

const MAX_ROWS = 5;
const SKELETON_KEYS = ['a', 'b', 'c'];

export function NeedsAttention(): JSX.Element {
  const items = useDashboardItems();

  const rows = items.data
    ? lowStockItems(items.data)
        .map(toLowStockVM)
        .sort((a, b) => a.pct - b.pct)
        .slice(0, MAX_ROWS)
    : [];

  return (
    <Card>
      <CardHeader
        title="Needs Attention"
        sub="Items below their minimum threshold"
        action={
          <ButtonLink to={`${routes.items}?status=attention`} variant="ghost" size="sm">
            All →
          </ButtonLink>
        }
      />
      {items.error ? (
        <LoadError
          error={items.error}
          title="Couldn't load low-stock items"
          onRetry={() => void items.refetch()}
        />
      ) : items.data === undefined ? (
        <div>
          {SKELETON_KEYS.map((key) => (
            <div className="mini-row" key={key}>
              <div className="l">
                <Skeleton width="60%" height={13} />
                <Skeleton width="40%" height={11} className="mt-8" />
              </div>
              <div className="stk">
                <Skeleton width={90} height={13} />
              </div>
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="empty">
          <div className="ttl">All stocked up</div>
          <div className="sub">Every item is above its reorder threshold.</div>
        </div>
      ) : (
        <div>
          {rows.map((row) => (
            <div className="mini-row" key={row.id}>
              <div className="l">
                <div className="t">{row.name}</div>
                <div className="m">{row.meta}</div>
              </div>
              <div className="stk">
                <div className="v">{row.value}</div>
                <ProgressBar
                  className="b"
                  value={row.pct}
                  tone={row.critical ? 'danger' : 'default'}
                  fillVar={row.critical ? undefined : 'var(--accent)'}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
