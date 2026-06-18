import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDateTime } from '@/lib/format';
import type { Activity } from '@/types/api.types';
import { ActivityType } from '@/types/enums';

import { useActivities } from '../hooks/useActivities';

const TYPE_LABELS: Record<ActivityType, string> = {
  [ActivityType.VISIT]: 'Visit',
  [ActivityType.MEETING]: 'Meeting',
  [ActivityType.FOLLOW_UP]: 'Follow-up',
  [ActivityType.CALL]: 'Call',
  [ActivityType.COMPLAINT]: 'Complaint',
};

export interface ActivityTimelineProps {
  customerId?: string;
  leadId?: string;
}

function TimelineRow({ activity }: { activity: Activity }): JSX.Element {
  return (
    <li className="timeline-item">
      <span className="timeline-dot" aria-hidden="true" />
      <div className="timeline-body">
        <div className="timeline-head">
          <Badge variant="info">{TYPE_LABELS[activity.type]}</Badge>
          <span className="timeline-time">{formatDateTime(activity.occurred_at)}</span>
          {activity.duration_minutes !== null && (
            <span className="timeline-duration">{activity.duration_minutes} min</span>
          )}
        </div>
        {activity.remarks && <p className="timeline-remarks">{activity.remarks}</p>}
      </div>
    </li>
  );
}

export function ActivityTimeline({ customerId, leadId }: ActivityTimelineProps): JSX.Element {
  const { data, isLoading } = useActivities({ customerId, leadId });

  if (isLoading) {
    return (
      <div className="flex col gap-12">
        <Skeleton height={48} />
        <Skeleton height={48} />
        <Skeleton height={48} />
      </div>
    );
  }

  const activities = data?.items ?? [];

  if (activities.length === 0) {
    return (
      <EmptyState
        icon="clock"
        title="No activities yet"
        sub="Logged visits, calls and meetings will appear here."
      />
    );
  }

  return (
    <ul className="timeline">
      {activities.map((activity) => (
        <TimelineRow key={activity.id} activity={activity} />
      ))}
    </ul>
  );
}
