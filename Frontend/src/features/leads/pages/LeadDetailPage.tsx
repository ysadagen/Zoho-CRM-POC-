import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ActivityTimeline } from '@/features/activities/components/ActivityTimeline';
import { LogActivityModal } from '@/features/activities/components/LogActivityModal';
import { formatDate, formatDateTime } from '@/lib/format';
import { LeadStage } from '@/types/enums';

import { LeadFormDrawer } from '../components/LeadFormDrawer';
import { LeadScorePanel } from '../components/LeadScorePanel';
import { StageTransitionModal } from '../components/StageTransitionModal';
import { ALLOWED_TRANSITIONS } from '../lead.transitions';
import { useLead, useLeadScore } from '../hooks/useLeads';
import '../leads.css';

const STAGE_VARIANT: Record<LeadStage, BadgeVariant> = {
  [LeadStage.NEW]: 'ink',
  [LeadStage.QUALIFICATION]: 'info',
  [LeadStage.NEGOTIATION]: 'warn',
  [LeadStage.WON]: 'success',
  [LeadStage.LOST]: 'danger',
};

function Fact({ label, value }: { label: string; value: string | null }): JSX.Element {
  return (
    <>
      <span className="muted fs-12">{label}</span>
      <span className="fs-12">{value && value.trim() !== '' ? value : '—'}</span>
    </>
  );
}

export function LeadDetailPage(): JSX.Element {
  const { id = '' } = useParams<{ id: string }>();
  const leadQuery = useLead(id);
  const scoreQuery = useLeadScore(id);
  const [editOpen, setEditOpen] = useState(false);
  const [transitionOpen, setTransitionOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);

  if (leadQuery.isError && !leadQuery.data) {
    return <PageError error={leadQuery.error} onRetry={() => void leadQuery.refetch()} />;
  }

  const lead = leadQuery.data;
  const canTransition = lead ? ALLOWED_TRANSITIONS[lead.stage].length > 0 : false;
  const location = lead
    ? [lead.city, lead.district, lead.state, lead.pincode].filter(Boolean).join(', ')
    : '';

  return (
    <>
      <PageHeader
        title={lead ? `${lead.lead_number} · ${lead.contact_name}` : 'Lead'}
        sub="Lead detail, live score, and activity"
        actions={
          lead && (
            <div className="flex gap-8">
              <Button variant="sec" onClick={() => setEditOpen(true)}>
                Edit
              </Button>
              <Button variant="sec" icon="plus" onClick={() => setLogOpen(true)}>
                Log activity
              </Button>
              {canTransition && (
                <Button variant="pri" onClick={() => setTransitionOpen(true)}>
                  Change stage
                </Button>
              )}
            </div>
          )
        }
      />

      <div className="lead-detail-grid">
        <div className="flex col gap-16">
          <Card pad>
            <CardHeader title="Details" />
            {leadQuery.isPending || !lead ? (
              <Skeleton height={140} />
            ) : (
              <div className="lead-facts">
                <span className="muted fs-12">Stage</span>
                <span>
                  <Badge variant={STAGE_VARIANT[lead.stage]}>{lead.stage}</Badge>
                </span>
                <Fact label="Source" value={lead.source.replace(/_/g, ' ')} />
                <Fact label="Phone" value={lead.phone} />
                <Fact label="Email" value={lead.email} />
                <Fact label="Location" value={location} />
                <Fact label="Estimated budget" value={lead.estimated_budget} />
                <Fact label="Dealer potential" value={lead.dealer_potential} />
                <Fact label="Required by" value={lead.required_by_date} />
                {lead.stage === LeadStage.WON && <Fact label="Won value" value={lead.won_value} />}
                {lead.stage === LeadStage.LOST && (
                  <Fact label="Lost reason" value={lead.lost_reason} />
                )}
              </div>
            )}
          </Card>

          <Card pad>
            <CardHeader title="Stage history" />
            {leadQuery.isPending || !lead ? (
              <Skeleton height={80} />
            ) : (
              <ul className="flex col gap-8">
                {lead.stage_history.map((h) => (
                  <li key={h.id} className="flex items-center gap-8 fs-12">
                    <Badge variant={STAGE_VARIANT[h.to_stage]}>{h.to_stage}</Badge>
                    <span className="muted">{formatDateTime(h.changed_at)}</span>
                    {h.remark && <span className="muted">— {h.remark}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card pad>
            <CardHeader title="Activity" />
            <ActivityTimeline leadId={id} />
          </Card>
        </div>

        <Card pad>
          <CardHeader title="Lead score" />
          {scoreQuery.isPending ? (
            <Skeleton height={180} />
          ) : scoreQuery.isError || !scoreQuery.data ? (
            <p className="muted fs-12">
              Score unavailable. The Intelligence service may be offline.
            </p>
          ) : (
            <>
              <LeadScorePanel score={scoreQuery.data} />
              <p className="muted fs-12 mt-8">
                Last computed {formatDate(scoreQuery.data.computed_at)}.
              </p>
            </>
          )}
        </Card>
      </div>

      {editOpen && lead && (
        <LeadFormDrawer mode="edit" lead={lead} onClose={() => setEditOpen(false)} />
      )}
      {transitionOpen && lead && (
        <StageTransitionModal
          leadId={id}
          currentStage={lead.stage}
          onClose={() => setTransitionOpen(false)}
        />
      )}
      {logOpen && <LogActivityModal leadId={id} onClose={() => setLogOpen(false)} />}
    </>
  );
}
