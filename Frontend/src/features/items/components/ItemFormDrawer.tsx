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
import { ItemType } from '@/types/enums';

import { useCreateItem, useItemsList, useUpdateItem } from '../hooks/useItems';
import {
  ITEM_UNITS,
  itemCreateSchema,
  itemEditSchema,
  type ItemCreateValues,
} from '../item.schema';
import { IngredientsEditor } from './IngredientsEditor';
import { itemToEditValues, toCreatePayload, toUpdatePayload } from '../item.transform';
import {
  DOSAGE_FORM_OPTIONS,
  DRUG_SCHEDULE_OPTIONS,
  MATERIAL_CLASSIFICATION_OPTIONS,
  PHARMACOPOEIA_OPTIONS,
  STORAGE_CONDITION_OPTIONS,
  type Option,
} from '../pharma';

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
  storage_condition: '',
  shelf_life_days: '',
  // RAW detail
  material_classification: '',
  pharmacopoeia: '',
  is_hazardous: false,
  // FINISHED detail
  generic_name: '',
  brand_name: '',
  strength: '',
  dosage_form: '',
  pack_size: '',
  ingredients: '',
  container_specification: '',
  selling_price: '',
  license_number: '',
  registration_code: '',
  mrp: '',
  drug_schedule: '',
  is_prescription_required: false,
};

/** Top-level form field keys we can route a Backend 422 `field` to. */
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
  'storage_condition',
  'shelf_life_days',
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
 * PATCH sku/type/stock, so in edit mode those are shown read-only. The pharma
 * detail section follows `type`: raw materials vs finished products.
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
    watch,
    setValue,
    formState: { errors },
  } = useForm<ItemCreateValues>({
    resolver: isCreate
      ? zodResolver(itemCreateSchema)
      : (zodResolver(itemEditSchema) as Resolver<ItemCreateValues>),
    defaultValues:
      isCreate || !item
        ? EMPTY_CREATE
        : { ...EMPTY_CREATE, ...itemToEditValues(item), sku: item.sku, type: item.type },
  });

  const pending = createMut.isPending || updateMut.isPending;
  const currentType = watch('type');

  // Ingredients can be picked from existing raw materials (unit auto-fetched).
  // Only finished products show the ingredients editor, so only fetch then.
  const rawMaterialsQuery = useItemsList(
    { limit: 100, offset: 0, type: ItemType.RAW },
    { enabled: currentType === ItemType.FINISHED },
  );
  const rawMaterials = (rawMaterialsQuery.data?.items ?? []).map((it) => ({
    name: it.name,
    unit: it.unit_of_measure,
  }));

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
    } else if (item) {
      updateMut.mutate(toUpdatePayload(values, item.type), {
        onSuccess: (updated) => {
          toast.success(`${updated.name} updated.`);
          onClose();
        },
        onError: (error) => routeError(error, 'items.update'),
      });
    }
  };

  // Small local helpers to keep the (long) pharma form DRY + consistent.
  const enumField = (
    field: keyof ItemCreateValues,
    label: string,
    options: Option<string>[],
  ): JSX.Element => (
    <Field label={label} htmlFor={`item-${field}`} error={errors[field]?.message}>
      <Select id={`item-${field}`} invalid={!!errors[field]} {...register(field)}>
        <option value="">— none —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </Field>
  );

  const textField = (
    field: keyof ItemCreateValues,
    label: string,
    opts: { type?: string; hint?: string } = {},
  ): JSX.Element => (
    <Field label={label} htmlFor={`item-${field}`} hint={opts.hint} error={errors[field]?.message}>
      <Input
        id={`item-${field}`}
        type={opts.type}
        min={opts.type === 'number' ? '0' : undefined}
        step={opts.type === 'number' ? 'any' : undefined}
        invalid={!!errors[field]}
        {...register(field)}
      />
    </Field>
  );

  const checkRow = (field: keyof ItemCreateValues, label: string): JSX.Element => (
    <label className="check-row" htmlFor={`item-${field}`}>
      <input id={`item-${field}`} type="checkbox" {...register(field)} />
      {label}
    </label>
  );

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

        <div className="form-grid">
          <Field label="Unit of measure" htmlFor="item-unit" required error={errors.unit_of_measure?.message}>
            <Select id="item-unit" invalid={!!errors.unit_of_measure} {...register('unit_of_measure')}>
              {ITEM_UNITS.map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </Select>
          </Field>

          {isCreate &&
            textField('stock_quantity', 'Initial stock', { type: 'number', hint: 'Defaults to 0' })}

          {textField('reorder_threshold', 'Reorder threshold', {
            type: 'number',
            hint: 'Low-stock alert',
          })}
          {textField('unit_price', 'Unit price', { type: 'number' })}
        </div>

        <div className="divider" />
        <div className="sect-title">Storage &amp; shelf life</div>
        <div className="form-grid">
          {enumField('storage_condition', 'Storage condition', STORAGE_CONDITION_OPTIONS)}
          {textField('shelf_life_days', 'Shelf life (days)', { type: 'number' })}
        </div>

        {currentType === 'RAW' ? (
          <>
            <div className="divider" />
            <div className="sect-title">Raw material details</div>
            <div className="form-grid">
              {enumField('material_classification', 'Classification', MATERIAL_CLASSIFICATION_OPTIONS)}
              {enumField('pharmacopoeia', 'Pharmacopoeia', PHARMACOPOEIA_OPTIONS)}
            </div>
            {checkRow('is_hazardous', 'Hazardous material')}
          </>
        ) : (
          <>
            <div className="divider" />
            <div className="sect-title">Finished product details</div>
            <div className="form-grid">
              {textField('generic_name', 'Generic name')}
              {textField('brand_name', 'Brand name')}
              {textField('strength', 'Strength', { hint: 'e.g. 500 mg' })}
              {enumField('dosage_form', 'Dosage form', DOSAGE_FORM_OPTIONS)}
              {textField('pack_size', 'Pack size', { hint: 'e.g. 10x10' })}
              {textField('container_specification', 'Container spec')}
              {textField('selling_price', 'Selling price', { type: 'number' })}
              {textField('mrp', 'MRP', { type: 'number' })}
              {textField('license_number', 'License number')}
              {textField('registration_code', 'Registration code')}
              {enumField('drug_schedule', 'Drug schedule', DRUG_SCHEDULE_OPTIONS)}
            </div>
            <Field
              label="Ingredients"
              htmlFor="item-ingredient-0"
              hint="One row per ingredient — name, quantity and unit"
              error={errors.ingredients?.message}
            >
              <IngredientsEditor
                initialValue={watch('ingredients')}
                rawMaterials={rawMaterials}
                onChange={(json) => setValue('ingredients', json, { shouldDirty: true })}
              />
            </Field>
            {checkRow('is_prescription_required', 'Prescription required')}
          </>
        )}

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
