import { useMemo } from 'react';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';
import type { Item, PurchaseOrder } from '@/types/api.types';

import { useReceivePurchaseOrder } from '../hooks/usePurchaseOrders';
import { receiveDeltas } from '../po.transform';

export interface ReceivePoModalProps {
  po: PurchaseOrder;
  onClose: () => void;
  onReceived?: () => void;
}

export function ReceivePoModal({ po, onClose, onReceived }: ReceivePoModalProps): JSX.Element {
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const itemMap = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.items ?? []) map.set(item.id, item);
    return map;
  }, [itemsQuery.data]);

  const toast = useToast();
  const reportApiError = useApiError();
  const receiveMut = useReceivePurchaseOrder(po.id);

  const confirm = (): void => {
    receiveMut.mutate(undefined, {
      onSuccess: () => {
        toast.success('Stock updated.');
        onReceived?.();
        onClose();
      },
      onError: (error) => reportApiError(error, { scope: 'purchase-orders.receive' }),
    });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={`Receive ${po.po_number}`}
      sub="Stock will increase for each line below."
      tone="success"
      footer={
        <>
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" loading={receiveMut.isPending} onClick={confirm}>
            Confirm receive
          </Button>
        </>
      }
    >
      <div className="flex col gap-8">
        {receiveDeltas(po, itemMap).map((delta) => (
          <div key={delta.itemId} className="mono">
            {delta.label}
          </div>
        ))}
      </div>
    </Modal>
  );
}
