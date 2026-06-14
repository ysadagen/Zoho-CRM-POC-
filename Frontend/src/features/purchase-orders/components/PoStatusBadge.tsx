import { Badge } from '@/components/ui/Badge';
import type { PurchaseOrderStatus } from '@/types/enums';

import { poStatusBadge } from '../po.transform';

export function PoStatusBadge({ status }: { status: PurchaseOrderStatus }): JSX.Element {
  const spec = poStatusBadge(status);
  return (
    <Badge variant={spec.variant} dot>
      {spec.label}
    </Badge>
  );
}
