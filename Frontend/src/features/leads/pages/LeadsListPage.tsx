import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Pager } from '@/components/ui/Pager';
import type { Lead, LeadScoreListItem } from '@/types/api.types';
import { LeadClassification, LeadStage } from '@/types/enums';

import { LeadFormDrawer } from '../components/LeadFormDrawer';
import { LeadsTable } from '../components/LeadsTable';
import { LeadsToolbar } from '../components/LeadsToolbar';
import { useLeadScores, useLeadsList } from '../hooks/useLeads';

const DEFAULT_LIMIT = 25;

export function LeadsListPage(): JSX.Element {
  const navigate = useNavigate();
  const [stage, setStage] = useState<LeadStage | ''>('');
  const [classification, setClassification] = useState<LeadClassification | ''>('');
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    setOffset(0);
  }, [stage, classification, limit]);

  const leadsQuery = useLeadsList({ limit, offset, stage: stage || undefined });
  // Scores come from the Intelligence service; joined to the list by id.
  const scoresQuery = useLeadScores();

  const scoresByLead = useMemo<Record<string, LeadScoreListItem | undefined>>(() => {
    const map: Record<string, LeadScoreListItem> = {};
    for (const score of scoresQuery.data?.items ?? []) map[score.lead_id] = score;
    return map;
  }, [scoresQuery.data]);

  const leads: Lead[] = leadsQuery.data?.items ?? [];
  // Classification filter is applied client-side on the loaded page (the score
  // is owned by the Intelligence service, not the Backend list endpoint).
  const visibleLeads = classification
    ? leads.filter((l) => scoresByLead[l.id]?.classification === classification)
    : leads;

  return (
    <>
      <PageHeader
        title="Leads"
        sub="Sales opportunities, scored Hot / Medium / Cold by the Intelligence engine"
        actions={
          <Button variant="pri" icon="plus" onClick={() => setCreateOpen(true)}>
            Add Lead
          </Button>
        }
      />

      {leadsQuery.isError && !leadsQuery.data ? (
        <PageError error={leadsQuery.error} onRetry={() => void leadsQuery.refetch()} />
      ) : (
        <Card>
          <LeadsToolbar
            stage={stage}
            onStage={setStage}
            classification={classification}
            onClassification={setClassification}
          />
          <LeadsTable
            leads={visibleLeads}
            scoresByLead={scoresByLead}
            loading={leadsQuery.isPending}
            onAdd={() => setCreateOpen(true)}
          />
          {leadsQuery.data && leadsQuery.data.total > 0 && !classification && (
            <Pager
              total={leadsQuery.data.total}
              limit={limit}
              offset={offset}
              onChange={({ limit: nextLimit, offset: nextOffset }) => {
                setLimit(nextLimit);
                setOffset(nextOffset);
              }}
            />
          )}
        </Card>
      )}

      {createOpen && (
        <LeadFormDrawer
          mode="create"
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`${routes.leads}/${id}`)}
        />
      )}
    </>
  );
}
