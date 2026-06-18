import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency, formatQuantity } from '@/lib/format';
import type { Item } from '@/types/api.types';

import { ItemStatusBadge, ItemTypeBadge } from './ItemBadges';

const COL_COUNT = 9;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface ItemsTableProps {
  items: Item[];
  loading: boolean;
  onEdit: (item: Item) => void;
  onAddItem: () => void;
}

export function ItemsTable({ items, loading, onEdit, onAddItem }: ItemsTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>SKU</th>
            <th>Name</th>
            <th>Type</th>
            <th>Unit</th>
            <th className="right">Unit price</th>
            <th className="right">Stock</th>
            <th className="right">Reorder</th>
            <th>Status</th>
            <th className="right">Actions</th>
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
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="package"
                  title="No items found"
                  sub="Try clearing the filters, or add your first item."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAddItem}>
                      Add Item
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td className="mono muted">{item.sku}</td>
                <td>
                  <Link className="tbl-link" to={`${routes.items}/${item.id}`}>
                    {item.name}
                  </Link>
                </td>
                <td>
                  <ItemTypeBadge type={item.type} />
                </td>
                <td className="muted">{item.unit_of_measure}</td>
                <td className="right mono">{formatCurrency(item.unit_price)}</td>
                <td className="right mono">{formatQuantity(item.stock_quantity)}</td>
                <td className="right mono muted">
                  {item.reorder_threshold ? formatQuantity(item.reorder_threshold) : '—'}
                </td>
                <td>
                  <span className="flex items-center gap-8">
                    <ItemStatusBadge status={item.status} />
                    {!item.is_active && <Badge variant="ink">Inactive</Badge>}
                  </span>
                </td>
                <td className="right">
                  <Link className="btn btn-txt btn-sm" to={`${routes.items}/${item.id}`}>
                    View
                  </Link>
                  <button className="btn btn-txt btn-sm" type="button" onClick={() => onEdit(item)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
