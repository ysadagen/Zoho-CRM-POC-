import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import type { CustomerHealth } from '@/types/api.types';

const COL_COUNT = 5;

const SKELETON_ROWS: { key: string; nameW: string }[] = [
  { key: 'a', nameW: '52%' },
  { key: 'b', nameW: '61%' },
  { key: 'c', nameW: '45%' },
  { key: 'd', nameW: '58%' },
  { key: 'e', nameW: '50%' },
  { key: 'f', nameW: '64%' },
  { key: 'g', nameW: '48%' },
];

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
            SKELETON_ROWS.map(({ key, nameW }) => (
              <tr key={key}>
                <td><Skeleton width={nameW} height={14} /></td>
                <td><Skeleton width={60} height={22} className="sk-pill" /></td>
                <td className="right"><Skeleton width={36} height={14} /></td>
                <td className="right"><Skeleton width={32} height={14} /></td>
                <td className="right"><Skeleton width={32} height={14} /></td>
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
