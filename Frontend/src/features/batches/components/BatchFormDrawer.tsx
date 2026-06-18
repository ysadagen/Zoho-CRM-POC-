import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';

import { batchCreateSchema, EMPTY_BATCH, type BatchFormValues } from '../batch.schema';
import { BATCH_STATUS_OPTIONS, toBatchCreatePayload } from '../batch.transform';
import { useCreateBatch } from '../hooks/useBatches';

const FORM_ID = 'batch-form';

export interface BatchFormDrawerProps {
  onClose: () => void;
  onCreated?: (id: string) => void;
}

/**
 * Record an opening-balance lot for stock an item already has. This does NOT
 * change the item's stock total — it labels existing stock with a lot. New
 * stock arrives via PO receive. The Backend rejects a quantity exceeding the
 * item's unbatched remainder (409), surfaced as a danger toast.
 */
export function BatchFormDrawer({ onClose, onCreated }: BatchFormDrawerProps): JSX.Element {
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateBatch();
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const items = itemsQuery.data?.items ?? [];

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<BatchFormValues>({
    resolver: zodResolver(batchCreateSchema),
    defaultValues: EMPTY_BATCH,
  });

  const itemReg = register('item_id');

  const onValid = (values: BatchFormValues): void => {
    createMut.mutate(toBatchCreatePayload(values), {
      onSuccess: (batch) => {
        toast.success(`Lot ${batch.batch_number} recorded.`);
        onCreated?.(batch.id);
        onClose();
      },
      onError: (error) =>
        reportApiError(error, { scope: 'batches.create', fallbackMessage: 'Could not record the lot.' }),
    });
  };

  return (
    <Drawer open onClose={onClose} title="Record Lot">
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <p className="text-muted fs-12">
          Record a lot for stock the item already has — this doesn&apos;t change the stock total.
        </p>

        <Field label="Item" htmlFor="batch-item" required error={errors.item_id?.message}>
          <Select
            id="batch-item"
            invalid={!!errors.item_id}
            {...itemReg}
            onChange={(e) => {
              void itemReg.onChange(e);
              // Default the lot's unit cost to the item's catalog price (editable).
              const picked = items.find((i) => i.id === e.target.value);
              if (picked) setValue('unit_cost', picked.unit_price, { shouldDirty: true });
            }}
          >
            <option value="">Select an item…</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.sku} — {item.name}
              </option>
            ))}
          </Select>
        </Field>

        <div className="form-grid">
          <Field label="Batch number" htmlFor="batch-number" required error={errors.batch_number?.message}>
            <Input id="batch-number" invalid={!!errors.batch_number} {...register('batch_number')} />
          </Field>
          <Field label="Quantity" htmlFor="batch-qty" required error={errors.quantity?.message}>
            <Input
              id="batch-qty"
              type="number"
              min="0"
              step="any"
              invalid={!!errors.quantity}
              {...register('quantity')}
            />
          </Field>
          <Field label="Expiry date" htmlFor="batch-expiry" required error={errors.expiry_date?.message}>
            <Input
              id="batch-expiry"
              type="date"
              invalid={!!errors.expiry_date}
              {...register('expiry_date')}
            />
          </Field>
          <Field
            label="Manufacturing date"
            htmlFor="batch-mfg"
            error={errors.manufacturing_date?.message}
          >
            <Input id="batch-mfg" type="date" {...register('manufacturing_date')} />
          </Field>
          <Field label="Unit cost" htmlFor="batch-cost" error={errors.unit_cost?.message}>
            <Input
              id="batch-cost"
              type="number"
              min="0"
              step="any"
              invalid={!!errors.unit_cost}
              {...register('unit_cost')}
            />
          </Field>
          <Field label="Status" htmlFor="batch-status" error={errors.batch_status?.message}>
            <Select id="batch-status" {...register('batch_status')}>
              {BATCH_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field
          label="Storage location"
          htmlFor="batch-location"
          error={errors.storage_location?.message}
        >
          <Input id="batch-location" {...register('storage_location')} />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={createMut.isPending}>
            Record lot
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
