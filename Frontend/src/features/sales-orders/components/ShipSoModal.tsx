import { useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useItemsList } from '@/features/items/hooks/useItems';
import { itemKeys } from '@/features/items/items.keys';
import { useApiError } from '@/hooks/useApiError';
import { ApiError } from '@/lib/api/errors';
import type { Item, SalesOrder } from '@/types/api.types';

import { useShipSalesOrder } from '../hooks/useSalesOrders';
import { soKeys } from '../so.keys';
import { shipDeltas } from '../so.transform';

export interface ShipSoModalProps {
  so: SalesOrder;
  onClose: () => void;
  onShipped?: () => void;
}

export function ShipSoModal({ so, onClose, onShipped }: ShipSoModalProps): JSX.Element {
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  const toast = useToast();
  const reportApiError = useApiError();
  const queryClient = useQueryClient();
  const shipMut = useShipSalesOrder(so.id);

  const confirm = (): void => {
    shipMut.mutate(undefined, {
      onSuccess: () => {
        toast.success('Order shipped. Stock updated.');
        onShipped?.();
        onClose();
      },
      onError: (error) => {
        // 409 INSUFFICIENT_STOCK leaves the SO as DRAFT — offer a stock refresh
        // so the user can re-check availability after procuring more (§5).
        const isStock = error instanceof ApiError && error.code === 'INSUFFICIENT_STOCK';
        reportApiError(error, {
          scope: 'sales-orders.ship',
          action: isStock
            ? {
                label: 'Refresh stock',
                onClick: () => {
                  void queryClient.invalidateQueries({ queryKey: itemKeys.all });
                  void queryClient.invalidateQueries({ queryKey: soKeys.all });
                },
              }
            : undefined,
        });
        onClose();
      },
    });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Ship ${so.so_number}`}
      sub="Stock will decrease for each line below. This can't be undone."
      tone="danger"
      footer={
        <>
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" loading={shipMut.isPending} onClick={confirm}>
            Confirm ship
          </Button>
        </>
      }
    >
      <div className="flex col gap-8">
        {shipDeltas(so, itemMap).map((delta) => (
          <div key={delta.itemId} className="mono">
            {delta.label}
          </div>
        ))}
      </div>
    </Modal>
  );
}
