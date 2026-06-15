import { Badge } from '@/components/ui/Badge';
import type { BatchStatus } from '@/types/enums';

import { batchStatusBadge } from '../batch.transform';

export function BatchStatusBadge({ status }: { status: BatchStatus }): JSX.Element {
  const spec = batchStatusBadge(status);
  return (
    <Badge variant={spec.variant} dot>
      {spec.label}
    </Badge>
  );
}
