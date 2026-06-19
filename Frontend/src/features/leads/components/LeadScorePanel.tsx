import { ClassificationBadge } from '@/components/ui/ClassificationBadge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { LeadScore } from '@/types/api.types';

const PARAMETERS: { key: keyof LeadScore['components']; label: string }[] = [
  { key: 'urgency', label: 'Urgency' },
  { key: 'location', label: 'Location' },
  { key: 'contribution_margin', label: 'Contribution margin' },
  { key: 'quantity', label: 'Quantity' },
  { key: 'product_margin', label: 'Product margin' },
];

const DEFAULT_LABELS: Record<string, string> = {
  urgency: 'Urgency',
  location: 'Location',
  contribution_margin: 'Contribution margin',
  quantity: 'Quantity',
  product_margin: 'Product margin',
};

export interface LeadScorePanelProps {
  score: LeadScore;
}

/** The five-parameter lead-score breakdown (each 0–100, equally weighted),
 *  with a notice of which parameters fell back to a default. */
export function LeadScorePanel({ score }: LeadScorePanelProps): JSX.Element {
  return (
    <div className="flex col gap-12">
      <div className="flex items-center gap-8">
        <span className="fs-20 mono">{score.total_score.toFixed(2)}</span>
        <ClassificationBadge scale="lead" value={score.classification} />
        <span className="spacer" />
        <span className="muted fs-12">config v{score.config_version}</span>
      </div>

      <div className="flex col gap-8">
        {PARAMETERS.map(({ key, label }) => (
          <div key={key} className="lead-score-row">
            <span className="fs-12">{label}</span>
            <ProgressBar value={score.components[key]} />
            <span className="mono fs-12 val">{score.components[key]}</span>
          </div>
        ))}
      </div>

      {score.defaults_applied.length > 0 && (
        <p className="muted fs-12">
          Defaults applied (missing data):{' '}
          {score.defaults_applied.map((d) => DEFAULT_LABELS[d] ?? d).join(', ')}.
        </p>
      )}
    </div>
  );
}
