import { useState } from 'react';

import { useToast } from '@/components/toast/useToast';
import { Icon, type IconName } from '@/components/ui/Icon';
import { useApiError } from '@/hooks/useApiError';
import { cx } from '@/lib/cx';

import { triggerIngest } from '../api/crm.api';

type SyncState = 'idle' | 'syncing' | 'ok' | 'error';

/** Per-state glyph + its entrance animation. Keying the <Icon> by state
 *  remounts it, so the animation replays on every transition (submit-style
 *  spinner → success pop → error shake). */
const GLYPH: Record<SyncState, { icon: IconName; anim?: string }> = {
  idle: { icon: 'sync' },
  syncing: { icon: 'sync', anim: 'kpi-spin' },
  ok: { icon: 'check', anim: 'kpi-sync-pop' },
  error: { icon: 'close', anim: 'kpi-sync-shake' },
};

function elapsedLabel(since: Date): string {
  const minutes = Math.floor((Date.now() - since.getTime()) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes === 1) return '1 min ago';
  return `${minutes} min ago`;
}

/** KPI card that also acts as the Zoho sync trigger.
 *  The icon-pill is a button — click it to pull from Zoho.
 *  State is local: once the page unmounts the last-sync time resets. */
export function SyncZohoKpiCard(): JSX.Element {
  const [syncState, setSyncState] = useState<SyncState>('idle');
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const toast = useToast();
  const reportApiError = useApiError();

  function handleSync(): void {
    if (syncState === 'syncing') return;
    setSyncState('syncing');
    triggerIngest()
      .then((result) => {
        const now = new Date();
        if (result.ok) {
          setSyncState('ok');
          setLastSync(now);
          toast.success('Zoho Sync triggered — records are being pulled.');
        } else {
          setSyncState('error');
          setLastSync(now);
          toast.warn('Sync request sent, but the Integration Layer returned a non-OK status.');
        }
      })
      .catch((error: unknown) => {
        setSyncState('error');
        setLastSync(new Date());
        reportApiError(error, {
          scope: 'crm.trigger_ingest',
          fallbackMessage: 'Could not reach the Integration Layer.',
        });
      });
  }

  const value =
    syncState === 'idle'
      ? 'Not synced'
      : syncState === 'syncing'
        ? 'Syncing…'
        : syncState === 'ok'
          ? 'Connected'
          : 'Sync failed';

  const delta = lastSync
    ? `Last sync · ${elapsedLabel(lastSync)}`
    : 'Click icon to pull Zoho data';

  const deltaDir: 'up' | 'down' | undefined =
    syncState === 'ok' ? 'up' : syncState === 'error' ? 'down' : undefined;

  const glyph = GLYPH[syncState];

  return (
    <div className="kpi crm">
      <button
        type="button"
        className="kpi-sync-btn icon-pill"
        data-sync-state={syncState}
        onClick={handleSync}
        disabled={syncState === 'syncing'}
        aria-label="Sync from Zoho CRM"
        title="Sync from Zoho CRM"
      >
        <Icon key={syncState} name={glyph.icon} size={14} className={glyph.anim} />
      </button>
      <div className="label">CRM Sync</div>
      <div className="val">{value}</div>
      <div className={cx('delta', deltaDir)}>{delta}</div>
    </div>
  );
}
