import { Badge } from '@/components/ui/Badge';
import type { ItemStatus, ItemType } from '@/types/enums';

import { itemStatusBadge, itemTypeBadge } from '../item.transform';

export function ItemTypeBadge({ type }: { type: ItemType }): JSX.Element {
  const spec = itemTypeBadge(type);
  return <Badge variant={spec.variant}>{spec.label}</Badge>;
}

export function ItemStatusBadge({ status }: { status: ItemStatus }): JSX.Element {
  const spec = itemStatusBadge(status);
  return (
    <Badge variant={spec.variant} dot>
      {spec.label}
    </Badge>
  );
}
