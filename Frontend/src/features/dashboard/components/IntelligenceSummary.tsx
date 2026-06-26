import { useMemo } from 'react';

import { Card, CardHeader } from '@/components/ui/Card';
import { KpiCard } from '@/components/ui/KpiCard';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Skeleton } from '@/components/ui/Skeleton';
import type { HealthClassification } from '@/types/enums';
import { LeadStage } from '@/types/enums';

import {
  useCustomerHealthSummary,
  useHotLeadCount,
  useLeadFunnelSource,
} from '../hooks/useIntelligenceSummary';

const AT_RISK_BANDS: HealthClassification[] = ['AT_RISK', 'CRITICAL'];

const FUNNEL: { stage: LeadStage; label: string }[] = [
  { stage: LeadStage.NEW, label: 'New' },
  { stage: LeadStage.QUALIFICATION, label: 'Qualification' },
  { stage: LeadStage.NEGOTIATION, label: 'Negotiation' },
  { stage: LeadStage.WON, label: 'Won' },
  { stage: LeadStage.LOST, label: 'Lost' },
];

/** Dashboard widget summarising the AI-scoring signals: hot leads, at-risk
 *  customers, and the lead funnel (NEW → … → WON/LOST). */
export function IntelligenceSummary(): JSX.Element {
  const hotQuery = useHotLeadCount();
  const healthQuery = useCustomerHealthSummary();
  const funnelQuery = useLeadFunnelSource();

  const atRiskCount = useMemo(
    () =>
      (healthQuery.data?.items ?? []).filter((c) =>
        AT_RISK_BANDS.includes(c.classification),
      ).length,
    [healthQuery.data],
  );

  const funnelCounts = useMemo(() => {
    const counts: Record<LeadStage, number> = {
      [LeadStage.NEW]: 0,
      [LeadStage.QUALIFICATION]: 0,
      [LeadStage.NEGOTIATION]: 0,
      [LeadStage.WON]: 0,
      [LeadStage.LOST]: 0,
    };
    for (const lead of funnelQuery.data?.items ?? []) counts[lead.stage] += 1;
    return counts;
  }, [funnelQuery.data]);

  const funnelMax = Math.max(1, ...FUNNEL.map((f) => funnelCounts[f.stage]));

  return (
    <Card pad>
      <CardHeader title="Sales intelligence" sub="Live AI signals" />
      <div className="kpi-row kpi-2 mt-8">
        <KpiCard
          tone="danger"
          icon="bell"
          label="Hot leads"
          value={hotQuery.isPending ? '—' : String(hotQuery.data?.total ?? 0)}
        />
        <KpiCard
          tone="info"
          icon="eye"
          label="At-risk customers"
          value={healthQuery.isPending ? '—' : String(atRiskCount)}
        />
      </div>

      <div className="mt-16">
        <h3 className="fs-12 muted">Lead funnel</h3>
        {funnelQuery.isPending ? (
          <Skeleton height={120} />
        ) : (
          <div className="flex col gap-8 mt-8">
            {FUNNEL.map(({ stage, label }) => (
              <div key={stage} className="funnel-row">
                <span className="fs-12">{label}</span>
                <ProgressBar value={funnelCounts[stage]} max={funnelMax} />
                <span className="mono fs-12 val">{funnelCounts[stage]}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
