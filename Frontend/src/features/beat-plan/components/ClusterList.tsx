import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import type { BeatCluster } from '@/types/api.types';

export interface ClusterListProps {
  clusters: BeatCluster[];
}

function formatPercent(lds: number): string {
  return `${Math.round(lds * 100)}%`;
}

export function ClusterList({ clusters }: ClusterListProps): JSX.Element {
  if (clusters.length === 0) {
    return (
      <EmptyState
        icon="truck"
        title="No district clusters"
        sub="Clusters appear once the rep has customers across districts."
      />
    );
  }

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>District</th>
            <th className="right">Customers</th>
            <th className="right">Density</th>
            <th>Opportunity</th>
          </tr>
        </thead>
        <tbody>
          {clusters.map((cluster) => (
            <tr key={cluster.district}>
              <td>{cluster.district}</td>
              <td className="right">{cluster.customer_count}</td>
              <td className="right">{formatPercent(cluster.lds)}</td>
              <td>
                {cluster.cluster_opportunity && (
                  <Badge variant="success" dot>
                    Cluster opportunity
                  </Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
