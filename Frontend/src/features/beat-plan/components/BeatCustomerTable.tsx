import { Badge } from '@/components/ui/Badge';
import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatCurrency } from '@/lib/format';
import type { BeatCustomer } from '@/types/api.types';

const COL_COUNT = 9;

export interface BeatCustomerTableProps {
  customers: BeatCustomer[];
  /** IDs in the suggested beat — these rows carry a visual marker. */
  suggestedIds?: ReadonlySet<string>;
}

function formatGap(days: number | null): string {
  if (days === null) return 'Never';
  return `${days}d`;
}

export function BeatCustomerTable({
  customers,
  suggestedIds,
}: BeatCustomerTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Customer</th>
            <th>District</th>
            <th>Type</th>
            <th className="right">VPS</th>
            <th>Priority</th>
            <th className="right">Last visit</th>
            <th className="right">Revenue 90d</th>
            <th className="right">Rev / Gap / Type / Loc</th>
            <th>Beat</th>
          </tr>
        </thead>
        <tbody>
          {customers.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="user"
                  title="No customers to plan"
                  sub="The rep has no handled customers for a beat yet."
                />
              </td>
            </tr>
          ) : (
            customers.map((c) => {
              const inBeat = suggestedIds?.has(c.customer_id) ?? false;
              return (
                <tr key={c.customer_id}>
                  <td>{c.company_name}</td>
                  <td>{c.district ?? '—'}</td>
                  <td>{c.customer_type}</td>
                  <td className="right">{c.vps}</td>
                  <td>
                    <ClassificationBadge scale="priority" value={c.priority} />
                  </td>
                  <td className="right">{formatGap(c.days_since_last_visit)}</td>
                  <td className="right">{formatCurrency(c.revenue_90d)}</td>
                  <td className="right mono fs-12">
                    {c.breakdown.revenue_score} / {c.breakdown.visit_gap_score} /{' '}
                    {c.breakdown.customer_type_score} / {c.breakdown.location_density_score}
                  </td>
                  <td>
                    {inBeat && (
                      <Badge variant="purple" dot>
                        In beat
                      </Badge>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
