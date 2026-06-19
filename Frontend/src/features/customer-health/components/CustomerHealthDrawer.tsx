import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { Drawer } from '@/components/ui/Drawer';
import { PageError } from '@/components/errors/PageError';
import { Skeleton } from '@/components/ui/Skeleton';
import type {
  CustomerHealthCpsComponents,
  CustomerHealthCrsComponents,
} from '@/types/api.types';

import { useCustomerHealth } from '../hooks/useCustomerHealth';

export interface CustomerHealthDrawerProps {
  customerId: string;
  onClose: () => void;
}

const CPS_LABELS: Record<keyof CustomerHealthCpsComponents, string> = {
  volume_achievement: 'Volume achievement',
  payment_discipline: 'Payment discipline',
  engagement: 'Engagement',
  growth_trend: 'Growth trend',
  margin_quality: 'Margin quality',
};

const CRS_LABELS: Record<keyof CustomerHealthCrsComponents, string> = {
  volume_decline: 'Volume decline',
  payment_risk: 'Payment risk',
  competitive_risk: 'Competitive risk',
  engagement_gap: 'Engagement gap',
  service_risk: 'Service risk',
};

interface BreakdownRow {
  label: string;
  value: number;
}

function Breakdown({
  title,
  total,
  rows,
}: {
  title: string;
  total: number;
  rows: BreakdownRow[];
}): JSX.Element {
  return (
    <section className="ch-breakdown">
      <div className="card-head">
        <h3>{title}</h3>
        <span className="mono">{total}</span>
      </div>
      <table className="tbl">
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="muted">{row.label}</td>
              <td className="right mono">{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function cpsRows(c: CustomerHealthCpsComponents): BreakdownRow[] {
  return (Object.keys(CPS_LABELS) as (keyof CustomerHealthCpsComponents)[]).map((key) => ({
    label: CPS_LABELS[key],
    value: c[key],
  }));
}

function crsRows(c: CustomerHealthCrsComponents): BreakdownRow[] {
  return (Object.keys(CRS_LABELS) as (keyof CustomerHealthCrsComponents)[]).map((key) => ({
    label: CRS_LABELS[key],
    value: c[key],
  }));
}

export function CustomerHealthDrawer({
  customerId,
  onClose,
}: CustomerHealthDrawerProps): JSX.Element {
  const query = useCustomerHealth(customerId);
  const detail = query.data;

  return (
    <Drawer open onClose={onClose} title={detail?.company_name ?? 'Customer Health'}>
      {query.isError && !detail ? (
        <PageError error={query.error} onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <Skeleton height={120} />
      ) : detail ? (
        <div className="flex col gap-8">
          <ClassificationBadge scale="health" value={detail.classification} />
          <Breakdown
            title="Customer Performance Score (CPS)"
            total={detail.cps}
            rows={cpsRows(detail.cps_components)}
          />
          <Breakdown
            title="Customer Risk Score (CRS)"
            total={detail.crs}
            rows={crsRows(detail.crs_components)}
          />
          {detail.defaults_applied.length > 0 && (
            <div className="muted fs-12">
              Defaults applied: {detail.defaults_applied.join(', ')}
            </div>
          )}
        </div>
      ) : null}
    </Drawer>
  );
}
