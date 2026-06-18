import { LeadClassification, LeadStage } from '@/types/enums';

export interface LeadsToolbarProps {
  stage: LeadStage | '';
  onStage: (value: LeadStage | '') => void;
  classification: LeadClassification | '';
  onClassification: (value: LeadClassification | '') => void;
}

const STAGE_OPTIONS: { value: LeadStage; label: string }[] = [
  { value: LeadStage.NEW, label: 'New' },
  { value: LeadStage.QUALIFICATION, label: 'Qualification' },
  { value: LeadStage.NEGOTIATION, label: 'Negotiation' },
  { value: LeadStage.WON, label: 'Won' },
  { value: LeadStage.LOST, label: 'Lost' },
];

const CLASSIFICATION_OPTIONS: { value: LeadClassification; label: string }[] = [
  { value: LeadClassification.HOT, label: 'Hot' },
  { value: LeadClassification.MEDIUM, label: 'Medium' },
  { value: LeadClassification.COLD, label: 'Cold' },
];

export function LeadsToolbar({
  stage,
  onStage,
  classification,
  onClassification,
}: LeadsToolbarProps): JSX.Element {
  return (
    <div className="toolbar">
      <label className="flex items-center gap-8">
        <span className="fs-12 muted">Stage</span>
        <select
          className="select"
          aria-label="Filter by stage"
          value={stage}
          onChange={(e) => onStage(e.target.value as LeadStage | '')}
        >
          <option value="">All stages</option>
          {STAGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-8">
        <span className="fs-12 muted">Score</span>
        <select
          className="select"
          aria-label="Filter by classification"
          value={classification}
          onChange={(e) => onClassification(e.target.value as LeadClassification | '')}
        >
          <option value="">All scores</option>
          {CLASSIFICATION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <span className="spacer" />
    </div>
  );
}
