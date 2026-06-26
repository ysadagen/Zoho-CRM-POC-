import { apiPost } from '@/lib/api/client';

export interface IngestTriggerResult {
  ok: boolean;
  [key: string]: unknown;
}

export function triggerIngest(): Promise<IngestTriggerResult> {
  return apiPost<IngestTriggerResult, Record<string, never>>('/api/v1/crm/trigger-ingest', {});
}
