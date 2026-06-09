import { useFieldArray, useFormContext } from 'react-hook-form';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { formatCurrency } from '@/lib/format';
import type { Item } from '@/types/api.types';

import { EMPTY_LINE, type PoFormValues } from '../po.schema';
import { lineTotal } from '../po.transform';

export interface PoLineItemsEditorProps {
  /** Pickable items (purchase orders buy RAW materials). */
  items: Item[];
}

export function PoLineItemsEditor({ items }: PoLineItemsEditorProps): JSX.Element {
  const {
    control,
    register,
    watch,
    formState: { errors },
  } = useFormContext<PoFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: 'items' });
  const lines = watch('items');

  return (
    <div className="line-items">
      <table className="tbl">
        <thead>
          <tr>
            <th>Item</th>
            <th className="right">Qty</th>
            <th className="right">Unit price</th>
            <th className="right">Line total</th>
            <th aria-label="Remove" />
          </tr>
        </thead>
        <tbody>
          {fields.map((field, i) => {
            const lineErrors = errors.items?.[i];
            const lt = lineTotal(lines?.[i]?.quantity ?? '', lines?.[i]?.unit_price ?? '');
            return (
              <tr key={field.id}>
                <td>
                  <Select
                    invalid={!!lineErrors?.item_id}
                    aria-label={`Item for line ${i + 1}`}
                    {...register(`items.${i}.item_id`)}
                  >
                    <option value="">Select an item…</option>
                    {items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.sku} — {item.name}
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
