import { useFieldArray, useFormContext } from 'react-hook-form';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { StockChip } from '@/components/ui/StockChip';
import { formatCurrency } from '@/lib/format';
import type { Item } from '@/types/api.types';

import { EMPTY_LINE, type SoFormValues } from '../so.schema';
import { lineTotal, soLineStock } from '../so.transform';

export interface SoLineItemsEditorProps {
  /** Pickable items (sales orders sell FINISHED products). */
  items: Item[];
}

export function SoLineItemsEditor({ items }: SoLineItemsEditorProps): JSX.Element {
  const {
    control,
    register,
    watch,
    formState: { errors },
  } = useFormContext<SoFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const lines = watch('items');
  const itemById = (id: string): Item | undefined => items.find((i) => i.id === id);

  return (
    <div className="line-items">
      <table className="tbl">
        <thead>
          <tr>
            <th>Item</th>
            <th className="right">Qty</th>
            <th>Stock</th>
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
            return (
              <tr key={field.id}>
                <td>
                  <Select
                    invalid={!!lineErrors?.item_id}
                    aria-label={`Item for line ${i + 1}`}
                    {...register(`items.${i}.item_id`)}
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
