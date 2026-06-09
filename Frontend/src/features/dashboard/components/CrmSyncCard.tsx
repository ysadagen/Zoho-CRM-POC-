import { Card, CardHeader } from '@/components/ui/Card';
import { Icon } from '@/components/ui/Icon';

/**
 * CRM sync activity is owned by the Integration Layer, which is a later phase
 * (Backend_Reference §13). Until it ships there is no sync data to show, so
 * this card is an honest placeholder rather than fabricated metrics.
 */
export function CrmSyncCard(): JSX.Element {
  return (
    <Card>
      <CardHeader
        title="CRM Sync"
        sub="Zoho CRM record activity"
        action={
          <button className="btn btn-ghost btn-sm" type="button" disabled title="Coming with the Integration Layer">
            Logs →
          </button>
        }
      />
      <div className="empty">
        <div className="ill">
          <Icon name="sync" size={28} />
        </div>
        <div className="ttl">Not connected yet</div>
        <div className="sub">
          Sync status will appear here once the Integration Layer is connected (a later phase).
        </div>
      </div>
    </Card>
  );
}
