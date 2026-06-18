import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { ButtonLink } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import type { Item } from '@/types/api.types';

import { toMovementVM } from '../dashboard.transform';
import { useDashboardItems, useRecentMovements } from '../hooks/useDashboard';
import { LoadError } from './LoadError';

const SKELETON_KEYS = ['a', 'b', 'c', 'd', 'e'];

export function RecentMovements(): JSX.Element {
  const movements = useRecentMovements();
  // Shares the cached catalog query with the KPI / Needs-Attention cards; used
  // only to resolve item_id → name + unit. Its own load state isn't gated on.
  const items = useDashboardItems();

  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of items.data ?? []) map.set(item.id, item);
    return map;
  }, [items.data]);

  return (
    <Card>
      <CardHeader
        title="Recent Stock Movements"
        sub="Live audit trail across the plant"
        action={
          <ButtonLink to={routes.stockMovements} variant="ghost" size="sm">
            View all →
          </ButtonLink>
        }
      />
      {movements.error ? (
        <LoadError
          error={movements.error}
          title="Couldn't load movements"
          onRetry={() => void movements.refetch()}
        />
      ) : movements.data === undefined ? (
        <table className="tbl tbl-center">
          <tbody>
            {SKELETON_KEYS.map((key) => (
              <tr key={key}>
                <td colSpan={5}>
                  <Skeleton height={16} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : movements.data.length === 0 ? (
        <div className="empty">
          <div className="ttl">No movements yet</div>
          <div className="sub">Stock changes from receiving POs and shipping SOs will appear here.</div>
        </div>
      ) : (
        <table className="tbl tbl-center">
          <thead>
            <tr>
              <th>Time</th>
              <th>Item</th>
              <th>Movement</th>
              <th>Quantity</th>
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            {movements.data.map((m) => {
              const row = toMovementVM(m, itemMap);
              return (
                <tr key={row.id}>
                  <td className="mono muted">{row.time}</td>
                  <td>
                    <Link className="tbl-link" to={`${routes.items}/${row.itemId}`}>
                      {row.item}
                    </Link>
                  </td>
                  <td>
                    <Badge variant={row.badgeVariant} dot>
                      {row.movement}
                    </Badge>
                  </td>
                  <td className="mono">{row.qty}</td>
                  <td className="muted">{row.reference}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Card>
  );
}
