import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';

import { useCreateAdjustment } from '../hooks/useStockMovements';
import { EMPTY_ADJUSTMENT, adjustmentSchema, type AdjustmentValues } from '../sm.schema';
import { toAdjustmentPayload } from '../sm.transform';

export interface ManualAdjustmentModalProps {
  onClose: () => void;
}

export function ManualAdjustmentModal({ onClose }: ManualAdjustmentModalProps): JSX.Element {
  const toast = useToast();
  const reportApiError = useApiError();
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const createMut = useCreateAdjustment();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AdjustmentValues>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: EMPTY_ADJUSTMENT,
  });

  const onValid = (values: AdjustmentValues): void => {
    createMut.mutate(toAdjustmentPayload(values), {
      onSuccess: () => {
        toast.success('Adjustment recorded.');
        onClose();
      },
      onError: (error) =>
        reportApiError(error, {
          scope: 'stock-movements.adjustment',
          fallbackMessage: 'Could not record the adjustment.',
        }),
    });
  };

  return (
    <Modal open onClose={onClose} title="Manual Adjustment" sub="Record a manual stock correction">
      <form className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Item" htmlFor="adj-item" required error={errors.item_id?.message}>
          <Select id="adj-item" invalid={!!errors.item_id} {...register('item_id')}>
            <option value="">Select an item…</option>
            {(itemsQuery.data?.items ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.sku} — {item.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Direction" htmlFor="adj-direction" required error={errors.direction?.message}>
          <Select id="adj-direction" {...register('direction')}>
            <option value="IN">Add to stock (IN)</option>
            <option value="OUT">Remove from stock (OUT)</option>
          </Select>
        </Field>

        <Field label="Quantity" htmlFor="adj-qty" required error={errors.quantity?.message}>
          <Input
            id="adj-qty"
            type="number"
            min="0"
            step="any"
            invalid={!!errors.quantity}
            {...register('quantity')}
          />
        </Field>

        <Field
          label="Reason note"
          htmlFor="adj-remarks"
          required
          hint="At least 10 characters — recorded for accountability"
          error={errors.remarks?.message}
        >
          <Textarea id="adj-remarks" invalid={!!errors.remarks} {...register('remarks')} />
        </Field>

        <div className="flex justify-end gap-8">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={createMut.isPending}>
            Record adjustment
          </Button>
        </div>
      </form>
    </Modal>
  );
}
