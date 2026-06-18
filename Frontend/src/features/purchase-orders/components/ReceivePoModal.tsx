import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo } from 'react';
import { useFieldArray, useForm, useWatch } from 'react-hook-form';

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
import { emptyReceiveLot, receiveDefaults, toReceivePayload } from '../po.transform';

const FORM_ID = 'po-receive-form';

export interface ReceivePoModalProps {
  po: PurchaseOrder;
  onClose: () => void;
  onReceived?: () => void;
}

/**
 * Receive a PO: the operator enters the lot (batch) details for each line —
 * batch number + expiry are required (pharma stock must enter with an expiry).
 * A line may be split across several lots ("Add lot"); the lots' quantities
 * must allocate the full line quantity before Confirm is enabled. On confirm,
 * the Backend creates a lot per row and posts the stock-in ledger.
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
    control,
    formState: { errors },
  } = useForm<PoReceiveValues>({
    resolver: zodResolver(poReceiveSchema),
    defaultValues: receiveDefaults(po),
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });

  // Live per-item allocation: the lots for a line must sum to its quantity.
  const watched = useWatch({ control, name: 'lines' });
  const allocatedByItem = useMemo(() => {
    const totals = new Map<string, number>();
    for (const lot of watched ?? []) {
      const n = Number(lot.quantity);
      if (Number.isFinite(n)) totals.set(lot.item_id, (totals.get(lot.item_id) ?? 0) + n);
    }
    return totals;
  }, [watched]);

  const hasMismatch = po.items.some(
    (line) => (allocatedByItem.get(line.item_id) ?? 0) !== Number(line.quantity),
  );

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
      sub="Enter each line's lot details — split a line across lots if it arrived in more than one batch."
      tone="success"
      footer={
        <>
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="pri"
            type="submit"
            form={FORM_ID}
            loading={receiveMut.isPending}
            disabled={hasMismatch}
          >
            Confirm receive
          </Button>
        </>
      }
    >
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        {po.items.map((line, lineIndex) => {
          const lots = fields
            .map((field, idx) => ({ field, idx }))
            .filter(({ field }) => field.item_id === line.item_id);
          const allocated = allocatedByItem.get(line.item_id) ?? 0;
          const expected = Number(line.quantity);
          const lineMismatch = allocated !== expected;

          return (
            <div key={line.id} className="flex col gap-8">
              {lineIndex > 0 && <div className="divider" />}
              <div className="strong">
                {itemMap.get(line.item_id)?.name ?? line.item_id}
                <span className="text-muted"> · {line.quantity}</span>
              </div>

              {lots.map(({ field, idx }, lotPos) => (
                <div key={field.id} className="flex col gap-8">
                  {lotPos > 0 && <div className="divider" />}
                  <div className="form-grid">
                    <Field
                      label="Batch number"
                      htmlFor={`recv-batch-${idx}`}
                      required
                      error={errors.lines?.[idx]?.batch_number?.message}
                    >
                      <Input
                        id={`recv-batch-${idx}`}
                        invalid={!!errors.lines?.[idx]?.batch_number}
                        {...register(`lines.${idx}.batch_number`)}
                      />
                    </Field>
                    <Field
                      label="Quantity"
                      htmlFor={`recv-qty-${idx}`}
                      required
                      error={errors.lines?.[idx]?.quantity?.message}
                    >
                      <Input
                        id={`recv-qty-${idx}`}
                        type="number"
                        step="any"
                        invalid={!!errors.lines?.[idx]?.quantity}
                        {...register(`lines.${idx}.quantity`)}
                      />
                    </Field>
                    <Field
                      label="Expiry date"
                      htmlFor={`recv-expiry-${idx}`}
                      required
                      error={errors.lines?.[idx]?.expiry_date?.message}
                    >
                      <Input
                        id={`recv-expiry-${idx}`}
                        type="date"
                        invalid={!!errors.lines?.[idx]?.expiry_date}
                        {...register(`lines.${idx}.expiry_date`)}
                      />
                    </Field>
                    <Field
                      label="Manufacturing date"
                      htmlFor={`recv-mfg-${idx}`}
                      error={errors.lines?.[idx]?.manufacturing_date?.message}
                    >
                      <Input
                        id={`recv-mfg-${idx}`}
                        type="date"
                        {...register(`lines.${idx}.manufacturing_date`)}
                      />
                    </Field>
                    <Field
                      label="Storage location"
                      htmlFor={`recv-loc-${idx}`}
                      error={errors.lines?.[idx]?.storage_location?.message}
                    >
                      <Input id={`recv-loc-${idx}`} {...register(`lines.${idx}.storage_location`)} />
                    </Field>
                  </div>
                  {lots.length > 1 && (
                    <div>
                      <Button variant="ghost" onClick={() => remove(idx)}>
                        Remove lot
                      </Button>
                    </div>
                  )}
                </div>
              ))}

              <div className="flex justify-between items-center gap-8">
                <span
                  className="text-muted"
                  style={lineMismatch ? { color: 'var(--danger)' } : undefined}
                >
                  {`Allocated ${allocated} / ${expected}`}
                </span>
                <Button variant="sec" onClick={() => append(emptyReceiveLot(line.item_id))}>
                  Add lot
                </Button>
              </div>
            </div>
          );
        })}
      </form>
    </Modal>
  );
}
