import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useApiError } from '@/hooks/useApiError';
import type { Item, VendorItemTerm } from '@/types/api.types';

import { useCreateTerm, useUpdateTerm } from '../hooks/useVendors';
import { EMPTY_TERM, vendorTermSchema, type VendorTermValues } from '../vendor.schema';
import { termToFormValues, toTermCreatePayload, toTermUpdatePayload } from '../vendor.transform';

const FORM_ID = 'vendor-term-form';

export interface VendorTermFormDrawerProps {
  vendorId: string;
  mode: 'create' | 'edit';
  term?: VendorItemTerm;
  items: Item[];
  onClose: () => void;
}

export function VendorTermFormDrawer({
  vendorId,
  mode,
  term,
  items,
  onClose,
}: VendorTermFormDrawerProps): JSX.Element {
  const isCreate = mode === 'create';
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateTerm(vendorId);
  const updateMut = useUpdateTerm(vendorId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<VendorTermValues>({
    resolver: zodResolver(vendorTermSchema),
    defaultValues: isCreate || !term ? EMPTY_TERM : termToFormValues(term),
  });

  const pending = createMut.isPending || updateMut.isPending;
  const itemName = (id: string): string => {
    const item = items.find((i) => i.id === id);
    return item ? `${item.sku} — ${item.name}` : id;
  };

  const onValid = (values: VendorTermValues): void => {
    if (isCreate) {
      createMut.mutate(toTermCreatePayload(values), {
        onSuccess: () => {
          toast.success('Item linked.');
          onClose();
        },
        onError: (error) => reportApiError(error, { scope: 'vendors.term.create', fallbackMessage: 'Could not link the item.' }),
      });
    } else if (term) {
      updateMut.mutate(
        { termId: term.id, body: toTermUpdatePayload(values) },
        {
          onSuccess: () => {
            toast.success('Terms updated.');
            onClose();
          },
          onError: (error) => reportApiError(error, { scope: 'vendors.term.update', fallbackMessage: 'Could not update the terms.' }),
        },
      );
    }
  };

  return (
    <Drawer open onClose={onClose} title={isCreate ? 'Link item' : 'Edit terms'}>
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        {isCreate ? (
          <Field label="Item" htmlFor="term-item" required error={errors.item_id?.message}>
            <Select id="term-item" invalid={!!errors.item_id} {...register('item_id')}>
              <option value="">Select an item…</option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.sku} — {item.name}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <div className="label-pair">
            <span className="l">Item</span>
            <span className="v">{itemName(term?.item_id ?? '')}</span>
          </div>
        )}

        <Field label="Rate" htmlFor="term-rate" required error={errors.rate?.message}>
          <Input id="term-rate" type="number" min="0" step="any" invalid={!!errors.rate} {...register('rate')} />
        </Field>
        <Field label="Discount %" htmlFor="term-discount" hint="0–100" error={errors.discount_percent?.message}>
          <Input
            id="term-discount"
            type="number"
            min="0"
            max="100"
            step="any"
            invalid={!!errors.discount_percent}
            {...register('discount_percent')}
          />
        </Field>
        <Field label="Effective from" htmlFor="term-from" required error={errors.effective_from?.message}>
          <Input id="term-from" type="date" invalid={!!errors.effective_from} {...register('effective_from')} />
        </Field>
        <Field label="Effective to" htmlFor="term-to" hint="Leave blank for open-ended" error={errors.effective_to?.message}>
          <Input id="term-to" type="date" {...register('effective_to')} />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={pending}>
            {isCreate ? 'Link item' : 'Save terms'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
