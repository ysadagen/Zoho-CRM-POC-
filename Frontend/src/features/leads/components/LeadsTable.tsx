import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDate } from '@/lib/format';
import type { Lead, LeadScoreListItem } from '@/types/api.types';
import { LeadStage } from '@/types/enums';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

const STAGE_VARIANT: Record<LeadStage, BadgeVariant> = {
  [LeadStage.NEW]: 'ink',
  [LeadStage.QUALIFICATION]: 'info',
  [LeadStage.NEGOTIATION]: 'warn',
  [LeadStage.WON]: 'success',
  [LeadStage.LOST]: 'danger',
};

const STAGE_LABEL: Record<LeadStage, string> = {
  [LeadStage.NEW]: 'New',
  [LeadStage.QUALIFICATION]: 'Qualification',
  [LeadStage.NEGOTIATION]: 'Negotiation',
  [LeadStage.WON]: 'Won',
  [LeadStage.LOST]: 'Lost',
};

export interface LeadsTableProps {
  leads: Lead[];
  /** Latest score per lead id (from the Intelligence service), joined here. */
  scoresByLead: Record<string, LeadScoreListItem | undefined>;
  loading: boolean;
  onAdd: () => void;
}

export function LeadsTable({ leads, scoresByLead, loading, onAdd }: LeadsTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Lead</th>
            <th>Contact</th>
            <th>Stage</th>
            <th>Score</th>
            <th>Created</th>
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
          ) : leads.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="user"
                  title="No leads found"
                  sub="Try a different filter, or add your first lead."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAdd}>
                      Add Lead
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            leads.map((lead) => {
              const score = scoresByLead[lead.id];
              return (
                <tr key={lead.id}>
                  <td>
                    <Link className="tbl-link" to={`${routes.leads}/${lead.id}`}>
                      {lead.lead_number}
                    </Link>
                  </td>
                  <td>{lead.contact_name}</td>
                  <td>
                    <Badge variant={STAGE_VARIANT[lead.stage]}>{STAGE_LABEL[lead.stage]}</Badge>
                  </td>
                  <td>
                    {score ? (
                      <ClassificationBadge scale="lead" value={score.classification} />
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="muted">{formatDate(lead.created_at)}</td>
                  <td className="right">
                    <Link className="btn btn-txt btn-sm" to={`${routes.leads}/${lead.id}`}>
                      View
                    </Link>
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
