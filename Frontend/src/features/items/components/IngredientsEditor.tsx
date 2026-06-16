import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

import { parseIngredients, serializeIngredients, type IngredientLine } from '../item.transform';

interface Row {
  name: string;
  qty: string;
  unit: string;
}

/** A raw material an ingredient can be picked from (its unit is auto-fetched). */
export interface RawMaterialOption {
  name: string;
  unit: string;
}

const DATALIST_ID = 'item-ingredient-raw-materials';

/** Seed rows from the stored value: parsed JSON, legacy free text, or one blank. */
function seedRows(initial: string): Row[] {
  const parsed = parseIngredients(initial);
  if (parsed) return parsed.map((l) => ({ name: l.name, qty: l.qty ?? '', unit: l.unit ?? '' }));
  // Legacy free-text value → keep it as one row's name so nothing is lost.
  if (initial.trim()) return [{ name: initial.trim(), qty: '', unit: '' }];
  return [{ name: '', qty: '', unit: '' }];
}

export interface IngredientsEditorProps {
  /** The current stored ingredients string — used once to seed the rows. */
  initialValue: string;
  /** Emits the rows serialized back to the JSON string the Backend stores. */
  onChange: (json: string) => void;
  /**
   * Raw materials the operator can pick an ingredient from. Selecting one
   * auto-fills the unit; a name that isn't in the list is kept as-is (so a
   * not-yet-cataloged ingredient can still be added).
   */
  rawMaterials?: RawMaterialOption[];
}

/**
 * Structured ingredient input (#2): repeatable name / qty / unit rows that
 * serialize to the JSON string the Backend keeps in `finished_detail.ingredients`.
 *
 * Each name is a combobox over the available raw materials — pick one and its
 * unit is auto-fetched from the catalog, or type a free-text name for an
 * ingredient that doesn't exist in the database yet. The detail page renders
 * the same JSON back as readable lines.
 */
export function IngredientsEditor({
  initialValue,
  onChange,
  rawMaterials = [],
}: IngredientsEditorProps): JSX.Element {
  const [rows, setRows] = useState<Row[]>(() => seedRows(initialValue));

  const commit = (next: Row[]): void => {
    setRows(next);
    onChange(serializeIngredients(next as IngredientLine[]));
  };

  /** Set the name and, if it matches a raw material, auto-fetch its unit. */
  const setName = (index: number, name: string): void => {
    const match = rawMaterials.find((m) => m.name.toLowerCase() === name.trim().toLowerCase());
    commit(
      rows.map((row, i) => (i === index ? { ...row, name, ...(match ? { unit: match.unit } : {}) } : row)),
    );
  };
  const update = (index: number, key: 'qty' | 'unit', value: string): void =>
    commit(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  const add = (): void => commit([...rows, { name: '', qty: '', unit: '' }]);
  const remove = (index: number): void =>
    commit(rows.length > 1 ? rows.filter((_, i) => i !== index) : [{ name: '', qty: '', unit: '' }]);

  return (
    <div className="flex col gap-8">
      {rawMaterials.length > 0 && (
        <datalist id={DATALIST_ID}>
          {rawMaterials.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name}
            </option>
          ))}
        </datalist>
      )}
      {rows.map((row, i) => (
        // Index key is safe here: inputs are controlled, so values follow state.
        <div key={i} className="flex gap-8 items-center">
          <Input
            id={`item-ingredient-${i}`}
            aria-label={`Ingredient name ${i + 1}`}
            placeholder="Ingredient"
            list={rawMaterials.length > 0 ? DATALIST_ID : undefined}
            value={row.name}
            onChange={(e) => setName(i, e.target.value)}
          />
          <Input
            aria-label={`Ingredient quantity ${i + 1}`}
            placeholder="Qty"
            className="input-sm"
            value={row.qty}
            onChange={(e) => update(i, 'qty', e.target.value)}
          />
          <Input
            aria-label={`Ingredient unit ${i + 1}`}
            placeholder="Unit"
            className="input-sm"
            value={row.unit}
            onChange={(e) => update(i, 'unit', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-txt btn-sm row-x"
            aria-label={`Remove ingredient ${i + 1}`}
            onClick={() => remove(i)}
          >
            ✕
          </button>
        </div>
      ))}
      <div>
        <Button variant="sec" size="sm" icon="plus" onClick={add}>
          Add ingredient
        </Button>
      </div>
    </div>
  );
}
