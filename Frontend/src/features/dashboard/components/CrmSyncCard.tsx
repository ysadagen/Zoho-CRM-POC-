import { useState } from 'react';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Icon } from '@/components/ui/Icon';
import { useApiError } from '@/hooks/useApiError';

import { triggerIngest } from '../api/crm.api';

export function CrmSyncCard(): JSX.Element {
  const [syncing, setSyncing] = useState(false);
  const toast = useToast();
  const reportApiError = useApiError();

  const handleSync = (): void => {
    setSyncing(true);
    triggerIngest()
      .then((result) => {
        if (result.ok) {
          toast.success('Zoho Sync Triggered: the Integration Layer is pulling records.');
        } else {
          toast.warn('Sync request sent, but the Integration Layer returned a non-OK status.');
        }
      })
      .catch((error) => {
        reportApiError(error, {
          scope: 'crm.trigger_ingest',
          fallbackMessage: 'Could not reach the Integration Layer.',
        });
      })
      .finally(() => {
        setSyncing(false);
      });
  };

  return (
    <Card>
      <CardHeader
        title="CRM Sync"
        sub="Zoho CRM record activity"
        action={
          <button className="btn btn-ghost btn-sm" type="button" disabled title="Sync logs not yet available">
            Logs →
          </button>
        }
      />
      <div className="empty">
        <div className="ill">
          <Icon name="sync" size={28} />
        </div>
        <div className="ttl">Sync from Zoho CRM</div>
        <div className="sub">
          Pull the latest leads, contacts, and activities from Zoho via the Integration Layer.
        </div>
        <Button variant="pri" loading={syncing} onClick={handleSync}>
          Sync from Zoho
        </Button>
      </div>
    </Card>
  );
}
