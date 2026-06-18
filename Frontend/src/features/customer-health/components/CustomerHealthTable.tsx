import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import type { CustomerHealth } from '@/types/api.types';

const COL_COUNT = 5;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface CustomerHealthTableProps {
  rows: CustomerHealth[];
  loading: boolean;
  onSelect: (customerId: string) => void;
}

export function CustomerHealthTable({
  rows,
  loading,
  onSelect,
}: CustomerHealthTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Health</th>
            <th className="right">Health score</th>
            <th className="right">CPS</th>
            <th className="right">CRS</th>
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
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="user"
                  title="No health scores yet"
                  sub="Scores appear once the Intelligence service has computed them."
                />
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.customer_id}>
                <td>
                  <button
                    type="button"
                    className="tbl-link"
                    onClick={() => onSelect(row.customer_id)}
                  >
                    {row.company_name}
                  </button>
                </td>
                <td>
                  <ClassificationBadge scale="health" value={row.classification} />
                </td>
                <td className="right">{row.health_score}</td>
                <td className="right">{row.cps}</td>
                <td className="right">{row.crs}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
