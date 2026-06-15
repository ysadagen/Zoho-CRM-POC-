import { useMemo } from 'react';
import { useFieldArray, useFormContext } from 'react-hook-form';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { StockChip } from '@/components/ui/StockChip';
import { useBatchesList } from '@/features/batches/hooks/useBatches';
import { formatCurrency } from '@/lib/format';
import type { Batch, Item } from '@/types/api.types';

import { EMPTY_LINE, type SoFormValues } from '../so.schema';
import { lineTotal, shippableLotsByItem, soLineStock } from '../so.transform';

export interface SoLineItemsEditorProps {
  /** Pickable items (sales orders sell FINISHED products). */
  items: Item[];
}

export function SoLineItemsEditor({ items }: SoLineItemsEditorProps): JSX.Element {
  const {
    control,
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext<SoFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const lines = watch('items');
  const itemById = (id: string): Item | undefined => items.find((i) => i.id === id);

  // Shippable lots per item — for the optional "Ship from lot" picker (#9).
  // Blank picks First-Expiry-First-Out; choosing a lot ships from it.
  const batchesQuery = useBatchesList({ limit: 100, offset: 0 });
  const lotsByItem = useMemo(
    () => shippableLotsByItem(batchesQuery.data?.items ?? []),
    [batchesQuery.data],
  );
  const lotLabel = (lot: Batch, unit: string): string =>
    `${lot.batch_number} — ${lot.quantity} ${unit} (exp ${lot.expiry_date})`;

  return (
    <div className="line-items">
      <table className="tbl">
        <thead>
          <tr>
            <th>Item</th>
            <th className="right">Qty</th>
            <th>Stock</th>
            <th>Ship from lot</th>
            <th className="right">Unit price</th>
            <th className="right">Line total</th>
            <th aria-label="Remove" />
          </tr>
        </thead>
        <tbody>
          {fields.map((field, i) => {
            const lineErrors = errors.items?.[i];
            const line = lines?.[i];
            const item = itemById(line?.item_id ?? '');
            const stock = soLineStock(line?.quantity ?? '', item);
            const lt = lineTotal(line?.quantity ?? '', line?.unit_price ?? '');
            const itemReg = register(`items.${i}.item_id`);
            return (
              <tr key={field.id}>
                <td>
                  <Select
                    invalid={!!lineErrors?.item_id}
                    aria-label={`Item for line ${i + 1}`}
                    {...itemReg}
                    onChange={(e) => {
                      void itemReg.onChange(e);
                      // Auto-fill the unit price from the item's catalog price so
                      // it stays consistent with items/batches (still editable).
                      const picked = itemById(e.target.value);
                      if (picked) {
                        setValue(`items.${i}.unit_price`, picked.unit_price, {
                          shouldValidate: true,
                          shouldDirty: true,
                        });
                      }
                      // Lots are item-specific — clear any prior lot choice.
                      setValue(`items.${i}.batch_id`, '', { shouldDirty: true });
                    }}
                  >
                    <option value="">Select an item…</option>
                    {items.map((it) => (
                      <option key={it.id} value={it.id}>
                        {it.sku} — {it.name}
                      </option>
                    ))}
                  </Select>
                  {lineErrors?.item_id && <div className="err">{lineErrors.item_id.message}</div>}
                </td>
                <td className="right">
                  <Input
                    type="number"
                    min="0"
                    step="any"
                    className="input-sm"
                    invalid={!!lineErrors?.quantity}
                    aria-label={`Quantity for line ${i + 1}`}
                    {...register(`items.${i}.quantity`)}
                  />
                  {lineErrors?.quantity && <div className="err">{lineErrors.quantity.message}</div>}
                </td>
                <td>{stock && <StockChip variant={stock.variant}>{stock.label}</StockChip>}</td>
                <td>
                  <Select
                    className="input-sm"
                    aria-label={`Ship from lot for line ${i + 1}`}
                    disabled={!item}
                    {...register(`items.${i}.batch_id`)}
                  >
                    <option value="">Auto (FEFO)</option>
                    {(item ? (lotsByItem.get(item.id) ?? []) : []).map((lot) => (
                      <option key={lot.id} value={lot.id}>
                        {lotLabel(lot, item?.unit_of_measure ?? '')}
                      </option>
                    ))}
                  </Select>
                </td>
                <td className="right">
                  <Input
                    type="number"
                    min="0"
                    step="any"
                    className="input-sm"
                    placeholder="Auto"
                    aria-label={`Unit price for line ${i + 1}`}
                    {...register(`items.${i}.unit_price`)}
                  />
                </td>
                <td className="right mono">{lt != null ? formatCurrency(lt) : '—'}</td>
                <td className="right">
                  {fields.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-txt btn-sm row-x"
                      aria-label={`Remove line ${i + 1}`}
                      onClick={() => remove(i)}
                    >
                      ✕
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Button variant="sec" size="sm" icon="plus" onClick={() => append({ ...EMPTY_LINE })}>
        Add row
      </Button>
    </div>
  );
}
