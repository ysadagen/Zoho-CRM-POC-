import { Badge } from '@/components/ui/Badge';
import type { SalesOrderStatus } from '@/types/enums';

import { soStatusBadge } from '../so.transform';

export function SoStatusBadge({ status }: { status: SalesOrderStatus }): JSX.Element {
  const spec = soStatusBadge(status);
  return (
    <Badge variant={spec.variant} dot>
      {spec.label}
    </Badge>
  );
}
