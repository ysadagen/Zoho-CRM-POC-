import type { BadgeVariant } from '@/components/ui/Badge';
import type {
  FinishedItemDetailInput,
  Item,
  ItemCreateRequest,
  ItemUpdateRequest,
  RawItemDetailInput,
  StockMovement,
} from '@/types/api.types';
import { ItemStatus, ItemType, MovementDirection } from '@/types/enums';
import type {
  DosageForm,
  DrugSchedule,
  MaterialClassification,
  Pharmacopoeia,
  StorageCondition,
} from '@/types/enums';

import type { ItemCreateValues, ItemEditValues } from './item.schema';
import { ITEM_UNITS } from './item.schema';

export interface BadgeSpec {
  variant: BadgeVariant;
  label: string;
}

export function itemTypeBadge(type: ItemType): BadgeSpec {
  return type === ItemType.RAW
    ? { variant: 'info', label: 'RAW' }
    : { variant: 'purple', label: 'FINISHED' };
}

const STATUS_BADGE: Record<ItemStatus, BadgeSpec> = {
  [ItemStatus.IN_STOCK]: { variant: 'success', label: 'In stock' },
  [ItemStatus.LOW_STOCK]: { variant: 'warn', label: 'Low' },
  [ItemStatus.NO_STOCK]: { variant: 'danger', label: 'Out' },
};

export function itemStatusBadge(status: ItemStatus): BadgeSpec {
  return STATUS_BADGE[status];
}

/**
 * Maps the UI status segmented-filter value → the Backend `ItemStatus` bucket(s)
 * it means. These go to the server as a (repeatable) `status` filter, so the
 * filter is correct across the whole catalog — not just the loaded page.
 * `attention` is the dashboard "Needs Attention" view: low *or* out of stock.
 */
export const STATUS_FILTER_TO_STATUSES: Record<'ok' | 'low' | 'out' | 'attention', ItemStatus[]> = {
  ok: [ItemStatus.IN_STOCK],
  low: [ItemStatus.LOW_STOCK],
  out: [ItemStatus.NO_STOCK],
  attention: [ItemStatus.LOW_STOCK, ItemStatus.NO_STOCK],
};

export interface MovementSummary {
  lastMovementAt: string | null;
  totalInbound: number;
  totalOutbound: number;
}

/** Lifetime in/out totals + the most recent timestamp, for the detail stat cards. */
export function summariseMovements(movements: StockMovement[]): MovementSummary {
  let totalInbound = 0;
  let totalOutbound = 0;
  let lastMovementAt: string | null = null;
  for (const m of movements) {
    const qty = Number(m.quantity);
    if (m.direction === MovementDirection.IN) totalInbound += qty;
    else totalOutbound += qty;
    // created_at is ISO-8601 → lexicographic compare finds the latest.
    if (lastMovementAt === null || m.created_at > lastMovementAt) lastMovementAt = m.created_at;
  }
  return { lastMovementAt, totalInbound, totalOutbound };
}

/** RAW detail block from form values (drops blank optionals; keeps the boolean). */
function buildRawDetail(values: ItemEditValues): RawItemDetailInput {
  const detail: RawItemDetailInput = { is_hazardous: values.is_hazardous };
  if (values.material_classification) {
    detail.material_classification = values.material_classification as MaterialClassification;
  }
  if (values.pharmacopoeia) detail.pharmacopoeia = values.pharmacopoeia as Pharmacopoeia;
  return detail;
}

/** FINISHED detail block from form values (drops blank optionals; keeps the boolean). */
function buildFinishedDetail(values: ItemEditValues): FinishedItemDetailInput {
  const detail: FinishedItemDetailInput = {
    is_prescription_required: values.is_prescription_required,
  };
  if (values.generic_name) detail.generic_name = values.generic_name;
  if (values.brand_name) detail.brand_name = values.brand_name;
  if (values.strength) detail.strength = values.strength;
  if (values.dosage_form) detail.dosage_form = values.dosage_form as DosageForm;
  if (values.pack_size) detail.pack_size = values.pack_size;
  if (values.ingredients) detail.ingredients = values.ingredients;
  if (values.container_specification) detail.container_specification = values.container_specification;
  if (values.selling_price) detail.selling_price = values.selling_price;
  if (values.license_number) detail.license_number = values.license_number;
  if (values.registration_code) detail.registration_code = values.registration_code;
  if (values.mrp) detail.mrp = values.mrp;
  if (values.drug_schedule) detail.drug_schedule = values.drug_schedule as DrugSchedule;
  return detail;
}

/** Applies the common-pharma fields + the type-matched detail block onto a payload. */
function applyPharma(
  payload: ItemCreateRequest | ItemUpdateRequest,
  values: ItemEditValues,
  type: ItemType,
): void {
  if (values.storage_condition) payload.storage_condition = values.storage_condition as StorageCondition;
  if (values.shelf_life_days) payload.shelf_life_days = Number(values.shelf_life_days);
  if (type === ItemType.RAW) payload.raw_detail = buildRawDetail(values);
  else payload.finished_detail = buildFinishedDetail(values);
}

/** Form → POST body, dropping empty optionals so the Backend keeps its defaults. */
export function toCreatePayload(values: ItemCreateValues): ItemCreateRequest {
  const payload: ItemCreateRequest = {
    sku: values.sku,
    name: values.name,
    type: values.type,
    category: values.category,
    unit_of_measure: values.unit_of_measure,
    unit_price: values.unit_price,
  };
  if (values.description) payload.description = values.description;
  if (values.stock_quantity) payload.stock_quantity = values.stock_quantity;
  if (values.reorder_threshold) payload.reorder_threshold = values.reorder_threshold;
  applyPharma(payload, values, values.type);
  return payload;
}

/** Form → PATCH body. Only sends PATCH-safe fields (never sku/type/stock).
 * `type` comes from the item being edited — it's fixed, so it selects which
 * detail block to patch. */
export function toUpdatePayload(values: ItemEditValues, type: ItemType): ItemUpdateRequest {
  const payload: ItemUpdateRequest = {
    name: values.name,
    category: values.category,
    unit_of_measure: values.unit_of_measure,
    unit_price: values.unit_price,
  };
  if (values.description) payload.description = values.description;
  if (values.reorder_threshold) payload.reorder_threshold = values.reorder_threshold;
  applyPharma(payload, values, type);
  return payload;
}

export interface IngredientLine {
  name: string;
  qty?: string;
  unit?: string;
}

/**
 * Parse the finished-product `ingredients` field for readable display.
 *
 * The Backend stores it as free text that operators fill with a JSON map/array
 * of `{ name, qty, unit }`. Returns the parsed lines, or `null` when it isn't
 * structured JSON (the caller then shows the raw text verbatim).
 */
export function parseIngredients(raw: string | null): IngredientLine[] | null {
  if (!raw || !raw.trim()) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  const values =
    Array.isArray(data) ? data : data && typeof data === 'object' ? Object.values(data) : null;
  if (!values) return null;

  const lines: IngredientLine[] = [];
  for (const entry of values) {
    if (!entry || typeof entry !== 'object') continue;
    const record = entry as Record<string, unknown>;
    const name = typeof record.name === 'string' ? record.name : null;
    if (!name) continue;
    lines.push({
      name,
      qty: record.qty != null ? String(record.qty) : undefined,
      unit: typeof record.unit === 'string' ? record.unit : undefined,
    });
  }
  return lines.length > 0 ? lines : null;
}

/**
 * Serialize structured ingredient rows back to the JSON string the Backend
 * stores in `finished_detail.ingredients` (#2). Rows without a name are
 * dropped; an empty list serializes to `''` (the "not set" value). The output
 * round-trips through {@link parseIngredients}.
 */
export function serializeIngredients(lines: IngredientLine[]): string {
  const clean = lines
    .map((l) => ({ name: l.name.trim(), qty: (l.qty ?? '').trim(), unit: (l.unit ?? '').trim() }))
    .filter((l) => l.name)
    .map((l) => ({
      name: l.name,
      ...(l.qty ? { qty: l.qty } : {}),
      ...(l.unit ? { unit: l.unit } : {}),
    }));
  return clean.length > 0 ? JSON.stringify(clean) : '';
}

function toFormUnit(unit: string): ItemEditValues['unit_of_measure'] {
  // The form select only offers ITEM_UNITS; fall back to the first if the
  // Backend ever returns an unknown unit (POC data uses the known set).
  return (ITEM_UNITS as readonly string[]).includes(unit)
    ? (unit as ItemEditValues['unit_of_measure'])
    : ITEM_UNITS[0];
}

/** Seeds the edit form from an existing item (incl. the pharma detail block). */
export function itemToEditValues(item: Item): ItemEditValues {
  const raw = item.raw_detail;
  const finished = item.finished_detail;
  return {
    name: item.name,
    category: item.category ?? '',
    description: item.description ?? '',
    unit_of_measure: toFormUnit(item.unit_of_measure),
    reorder_threshold: item.reorder_threshold ?? '',
    unit_price: item.unit_price,
    storage_condition: item.storage_condition ?? '',
    shelf_life_days: item.shelf_life_days != null ? String(item.shelf_life_days) : '',
    // RAW detail (empty for a finished item).
    material_classification: raw?.material_classification ?? '',
    pharmacopoeia: raw?.pharmacopoeia ?? '',
    is_hazardous: raw?.is_hazardous ?? false,
    // FINISHED detail (empty for a raw item).
    generic_name: finished?.generic_name ?? '',
    brand_name: finished?.brand_name ?? '',
    strength: finished?.strength ?? '',
    dosage_form: finished?.dosage_form ?? '',
    pack_size: finished?.pack_size ?? '',
    ingredients: finished?.ingredients ?? '',
    container_specification: finished?.container_specification ?? '',
    selling_price: finished?.selling_price ?? '',
    license_number: finished?.license_number ?? '',
    registration_code: finished?.registration_code ?? '',
    mrp: finished?.mrp ?? '',
    drug_schedule: finished?.drug_schedule ?? '',
    is_prescription_required: finished?.is_prescription_required ?? false,
  };
}
