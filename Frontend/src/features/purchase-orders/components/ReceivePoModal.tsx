import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo } from 'react';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';
import type { Item, PurchaseOrder } from '@/types/api.types';

import { useReceivePurchaseOrder } from '../hooks/usePurchaseOrders';
import { poReceiveSchema, type PoReceiveValues } from '../po.schema';
import { receiveDefaults, toReceivePayload } from '../po.transform';

const FORM_ID = 'po-receive-form';

export interface ReceivePoModalProps {
  po: PurchaseOrder;
  onClose: () => void;
  onReceived?: () => void;
}

/**
 * Receive a PO: the operator enters the lot (batch) details for each line —
 * batch number + expiry are required (pharma stock must enter with an expiry).
 * On confirm, the Backend creates a lot per line and posts the stock-in ledger.
 */
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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PoReceiveValues>({
    resolver: zodResolver(poReceiveSchema),
    defaultValues: receiveDefaults(po),
  });

  const onValid = (values: PoReceiveValues): void => {
    receiveMut.mutate(toReceivePayload(values), {
      onSuccess: () => {
        toast.success('Stock received — lots created.');
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
      sub="Enter each line's lot details — stock increases and a lot is created per line."
      tone="success"
      footer={
        <>
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" form={FORM_ID} loading={receiveMut.isPending}>
            Confirm receive
          </Button>
        </>
      }
    >
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        {po.items.map((line, index) => (
          <div key={line.id} className="flex col gap-8">
            {index > 0 && <div className="divider" />}
            <div className="strong">
              {itemMap.get(line.item_id)?.name ?? line.item_id}
              <span className="text-muted"> · {line.quantity}</span>
            </div>
            <div className="form-grid">
              <Field
                label="Batch number"
                htmlFor={`recv-batch-${index}`}
                required
                error={errors.lines?.[index]?.batch_number?.message}
              >
                <Input
                  id={`recv-batch-${index}`}
                  invalid={!!errors.lines?.[index]?.batch_number}
                  {...register(`lines.${index}.batch_number`)}
                />
              </Field>
              <Field
                label="Expiry date"
                htmlFor={`recv-expiry-${index}`}
                required
                error={errors.lines?.[index]?.expiry_date?.message}
              >
                <Input
                  id={`recv-expiry-${index}`}
                  type="date"
                  invalid={!!errors.lines?.[index]?.expiry_date}
                  {...register(`lines.${index}.expiry_date`)}
                />
              </Field>
              <Field
                label="Manufacturing date"
                htmlFor={`recv-mfg-${index}`}
                error={errors.lines?.[index]?.manufacturing_date?.message}
              >
                <Input
                  id={`recv-mfg-${index}`}
                  type="date"
                  {...register(`lines.${index}.manufacturing_date`)}
                />
              </Field>
              <Field
                label="Storage location"
                htmlFor={`recv-loc-${index}`}
                error={errors.lines?.[index]?.storage_location?.message}
              >
                <Input id={`recv-loc-${index}`} {...register(`lines.${index}.storage_location`)} />
              </Field>
            </div>
          </div>
        ))}
      </form>
    </Modal>
  );
}
