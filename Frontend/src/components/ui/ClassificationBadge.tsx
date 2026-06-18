import { Badge, type BadgeVariant } from '@/components/ui/Badge';
import type {
  HealthClassification,
  LeadClassification,
  VisitPriority,
} from '@/types/enums';

/**
 * Maps an intelligence classification (lead band, customer-health band, or
 * beat visit-priority) to the shared {@link Badge} primitive — colour + text,
 * never colour alone (a11y). The `scale` discriminator disambiguates values
 * that overlap across scales (e.g. MEDIUM is amber for a lead but blue for a
 * visit priority).
 */

const LEAD: Record<LeadClassification, { variant: BadgeVariant; label: string }> = {
  HOT: { variant: 'danger', label: 'Hot' },
  MEDIUM: { variant: 'warn', label: 'Medium' },
  COLD: { variant: 'info', label: 'Cold' },
};

const HEALTH: Record<HealthClassification, { variant: BadgeVariant; label: string }> = {
  HEALTHY: { variant: 'success', label: 'Healthy' },
  STABLE: { variant: 'info', label: 'Stable' },
  AT_RISK: { variant: 'warn', label: 'At Risk' },
  CRITICAL: { variant: 'danger', label: 'Critical' },
};

const PRIORITY: Record<VisitPriority, { variant: BadgeVariant; label: string }> = {
  CRITICAL: { variant: 'danger', label: 'Critical' },
  HIGH: { variant: 'warn', label: 'High' },
  MEDIUM: { variant: 'info', label: 'Medium' },
  LOW: { variant: 'ink', label: 'Low' },
};

export type ClassificationBadgeProps = (
  | { scale: 'lead'; value: LeadClassification }
  | { scale: 'health'; value: HealthClassification }
  | { scale: 'priority'; value: VisitPriority }
) & {
  /** Leading status dot (defaults on — colour is never the only signal). */
  dot?: boolean;
  className?: string;
};

export function ClassificationBadge(props: ClassificationBadgeProps): JSX.Element {
  const { dot = true, className } = props;
  const entry =
    props.scale === 'lead'
      ? LEAD[props.value]
      : props.scale === 'health'
        ? HEALTH[props.value]
        : PRIORITY[props.value];
  return (
    <Badge variant={entry.variant} dot={dot} className={className}>
      {entry.label}
    </Badge>
  );
}
