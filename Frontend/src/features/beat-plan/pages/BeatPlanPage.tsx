import { useMemo, useState } from 'react';

import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Card, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import type { BeatCustomer } from '@/types/api.types';

import { BeatCustomerTable } from '../components/BeatCustomerTable';
import { ClusterList } from '../components/ClusterList';
import { useBeatPlan, useReps } from '../hooks/useBeatPlan';
import '../beatPlan.css';

export function BeatPlanPage(): JSX.Element {
  const [repUserId, setRepUserId] = useState('');
  const [maxVisitsInput, setMaxVisitsInput] = useState('');

  const repsQuery = useReps();
  const maxVisits = maxVisitsInput === '' ? undefined : Number(maxVisitsInput);
  const planQuery = useBeatPlan(repUserId, maxVisits);

  const plan = planQuery.data;
  const suggestedIds = useMemo(
    () => new Set<string>((plan?.suggested_beat ?? []).map((c: BeatCustomer) => c.customer_id)),
    [plan],
  );

  return (
    <>
      <PageHeader title="Beat Plan" sub="Who to visit next, clustered by district" />

      <Card pad>
        <div className="beat-toolbar">
          <Field label="Sales rep" htmlFor="beat-rep">
            <Select
              id="beat-rep"
              value={repUserId}
              onChange={(e) => setRepUserId(e.target.value)}
            >
              <option value="">Select a rep…</option>
              {(repsQuery.data?.items ?? []).map((rep) => (
                <option key={rep.id} value={rep.id}>
                  {rep.email}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Max visits" htmlFor="beat-max-visits">
            <input
              id="beat-max-visits"
              className="input"
              type="number"
              min={1}
              value={maxVisitsInput}
              placeholder={plan ? String(plan.max_visits) : ''}
              onChange={(e) => setMaxVisitsInput(e.target.value)}
            />
          </Field>
        </div>
      </Card>

      {planQuery.isError && !plan ? (
        <PageError error={planQuery.error} onRetry={() => void planQuery.refetch()} />
      ) : !repUserId ? (
        <Card pad>
          <EmptyState
            icon="truck"
            title="Select a rep to plan a beat"
            sub="Pick a sales rep to see who they should visit next."
          />
        </Card>
      ) : plan && plan.all_customers.length === 0 ? (
        <Card pad>
          <EmptyState
            icon="user"
            title="No customers to plan"
            sub="This rep has no handled customers for a beat yet."
          />
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader title="District clusters" sub="Where this rep's customers concentrate" />
            <ClusterList clusters={plan?.clusters ?? []} />
          </Card>

          <Card>
            <CardHeader
              title={`Suggested beat (top ${plan?.suggested_beat.length ?? 0})`}
              sub="The highest-priority visits for this trip"
            />
            <BeatCustomerTable customers={plan?.suggested_beat ?? []} suggestedIds={suggestedIds} />
          </Card>

          <Card>
            <CardHeader title="All customers" sub="Full ranked list by visit-priority score" />
            <BeatCustomerTable customers={plan?.all_customers ?? []} suggestedIds={suggestedIds} />
          </Card>
        </>
      )}
    </>
  );
}
