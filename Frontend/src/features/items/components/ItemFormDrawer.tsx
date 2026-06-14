import { zodResolver } from '@hookform/resolvers/zod';
import { useForm, type Resolver } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Textarea } from '@/components/ui/Textarea';
import { useApiError } from '@/hooks/useApiError';
import { ApiError } from '@/lib/api/errors';
import type { Item } from '@/types/api.types';

import { useCreateItem, useUpdateItem } from '../hooks/useItems';
import {
  ITEM_UNITS,
  itemCreateSchema,
  itemEditSchema,
  type ItemCreateValues,
} from '../item.schema';
import { itemToEditValues, toCreatePayload, toUpdatePayload } from '../item.transform';

const FORM_ID = 'item-form';

const EMPTY_CREATE: ItemCreateValues = {
  sku: '',
  type: 'RAW',
  stock_quantity: '',
  name: '',
  category: '',
  description: '',
  unit_of_measure: 'kg',
  reorder_threshold: '',
  unit_price: '',
};

/** Form field keys we can route a Backend 422 `field` to. */
const FORM_FIELDS = new Set<keyof ItemCreateValues>([
  'sku',
  'name',
  'category',
  'description',
  'type',
  'stock_quantity',
  'unit_of_measure',
  'reorder_threshold',
  'unit_price',
]);

export interface ItemFormDrawerProps {
  mode: 'create' | 'edit';
  /** Required in edit mode — the item being edited. */
  item?: Item;
  onClose: () => void;
  /** Create-only: called with the new id so the caller can navigate to detail. */
  onCreated?: (id: string) => void;
}

/**
 * Create/edit drawer. Mount it only while open (the caller conditionally
 * renders it) so each open starts from fresh form state. The Backend won't
 * PATCH sku/type/stock, so in edit mode those are shown read-only.
 */
export function ItemFormDrawer({ mode, item, onClose, onCreated }: ItemFormDrawerProps): JSX.Element {
  const isCreate = mode === 'create';
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateItem();
  const updateMut = useUpdateItem(item?.id ?? '');

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ItemCreateValues>({
    resolver: isCreate
      ? zodResolver(itemCreateSchema)
      : // Edit validates the PATCH-safe subset; create-only keys are stripped by
        // Zod. The value type stays the superset, so cast the narrower resolver.
        (zodResolver(itemEditSchema) as Resolver<ItemCreateValues>),
    defaultValues:
      isCreate || !item
        ? EMPTY_CREATE
        : { ...EMPTY_CREATE, ...itemToEditValues(item), sku: item.sku, type: item.type },
  });

  const pending = createMut.isPending || updateMut.isPending;

  const routeError = (error: unknown, scope: string): void => {
    if (error instanceof ApiError && error.isValidation() && error.field) {
      const field = error.field as keyof ItemCreateValues;
      if (FORM_FIELDS.has(field)) {
        setError(field, { message: error.message });
        return;
      }
    }
    reportApiError(error, { scope, fallbackMessage: 'Could not save the item.' });
  };

  const onValid = (values: ItemCreateValues): void => {
    if (isCreate) {
      createMut.mutate(toCreatePayload(values), {
        onSuccess: (created) => {
          toast.success(`${created.name} created.`);
          onCreated?.(created.id);
          onClose();
        },
        onError: (error) => routeError(error, 'items.create'),
      });
    } else {
      updateMut.mutate(toUpdatePayload(values), {
        onSuccess: (updated) => {
          toast.success(`${updated.name} updated.`);
          onClose();
        },
        onError: (error) => routeError(error, 'items.update'),
      });
    }
  };

  return (
    <Drawer open onClose={onClose} title={isCreate ? 'Add Item' : 'Edit Item'}>
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        {isCreate ? (
          <>
            <Field label="SKU" htmlFor="item-sku" required error={errors.sku?.message}>
              <Input id="item-sku" invalid={!!errors.sku} {...register('sku')} />
            </Field>
            <Field label="Type" htmlFor="item-type" required error={errors.type?.message}>
              <Select id="item-type" invalid={!!errors.type} {...register('type')}>
                <option value="RAW">Raw material</option>
                <option value="FINISHED">Finished product</option>
              </Select>
            </Field>
          </>
        ) : (
          <div className="flex gap-24">
            <div className="label-pair">
              <span className="l">SKU</span>
              <span className="v mono">{item?.sku}</span>
            </div>
            <div className="label-pair">
              <span className="l">Type</span>
              <span className="v">{item?.type === 'RAW' ? 'Raw material' : 'Finished product'}</span>
            </div>
          </div>
        )}

        <Field label="Name" htmlFor="item-name" required error={errors.name?.message}>
          <Input id="item-name" invalid={!!errors.name} {...register('name')} />
        </Field>

        <Field label="Category" htmlFor="item-category" required error={errors.category?.message}>
          <Input id="item-category" invalid={!!errors.category} {...register('category')} />
        </Field>

        <Field
          label="Description"
          htmlFor="item-description"
          hint="Up to 500 characters"
          error={errors.description?.message}
        >
          <Textarea
            id="item-description"
            invalid={!!errors.description}
            {...register('description')}
          />
        </Field>

        <Field label="Unit of measure" htmlFor="item-unit" required error={errors.unit_of_measure?.message}>
          <Select id="item-unit" invalid={!!errors.unit_of_measure} {...register('unit_of_measure')}>
            {ITEM_UNITS.map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </Select>
        </Field>

        {isCreate && (
          <Field
            label="Initial stock"
            htmlFor="item-stock"
            hint="Defaults to 0"
            error={errors.stock_quantity?.message}
          >
            <Input
              id="item-stock"
              type="number"
              min="0"
              step="any"
              invalid={!!errors.stock_quantity}
              {...register('stock_quantity')}
            />
          </Field>
        )}

        <Field
          label="Reorder threshold"
          htmlFor="item-threshold"
          hint="Used for low-stock alerts"
          error={errors.reorder_threshold?.message}
        >
          <Input
            id="item-threshold"
            type="number"
            min="0"
            step="any"
            invalid={!!errors.reorder_threshold}
            {...register('reorder_threshold')}
          />
        </Field>

        <Field label="Unit price" htmlFor="item-price" required error={errors.unit_price?.message}>
          <Input
            id="item-price"
            type="number"
            min="0"
            step="any"
            invalid={!!errors.unit_price}
            {...register('unit_price')}
          />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={pending}>
            {isCreate ? 'Create item' : 'Save changes'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
