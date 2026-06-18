/**
 * Human-readable options + label lookups for the pharma enums.
 *
 * Single source of truth for how the UI renders `storage_condition`,
 * `material_classification`, `pharmacopoeia`, `dosage_form`, and
 * `drug_schedule` — used by item forms (selects) and read views (labels).
 */
import {
  DosageForm,
  DrugSchedule,
  MaterialClassification,
  Pharmacopoeia,
  StorageCondition,
} from '@/types/enums';

export interface Option<T extends string> {
  value: T;
  label: string;
}

export const STORAGE_CONDITION_OPTIONS: Option<StorageCondition>[] = [
  { value: StorageCondition.AMBIENT, label: 'Ambient' },
  { value: StorageCondition.COLD_CHAIN_2_8, label: 'Cold chain (2–8°C)' },
  { value: StorageCondition.FROZEN, label: 'Frozen' },
  { value: StorageCondition.CONTROLLED, label: 'Controlled room temp' },
];

export const MATERIAL_CLASSIFICATION_OPTIONS: Option<MaterialClassification>[] = [
  { value: MaterialClassification.API, label: 'Active (API)' },
  { value: MaterialClassification.EXCIPIENT, label: 'Excipient' },
  { value: MaterialClassification.SOLVENT, label: 'Solvent' },
  { value: MaterialClassification.REAGENT, label: 'Reagent' },
  { value: MaterialClassification.PACKAGING, label: 'Packaging' },
];

export const PHARMACOPOEIA_OPTIONS: Option<Pharmacopoeia>[] = [
  { value: Pharmacopoeia.IP, label: 'IP' },
  { value: Pharmacopoeia.BP, label: 'BP' },
  { value: Pharmacopoeia.USP, label: 'USP' },
  { value: Pharmacopoeia.EP, label: 'EP' },
  { value: Pharmacopoeia.JP, label: 'JP' },
  { value: Pharmacopoeia.NONE, label: 'None' },
];

export const DOSAGE_FORM_OPTIONS: Option<DosageForm>[] = [
  { value: DosageForm.TABLET, label: 'Tablet' },
  { value: DosageForm.CAPSULE, label: 'Capsule' },
  { value: DosageForm.SYRUP, label: 'Syrup' },
  { value: DosageForm.SUSPENSION, label: 'Suspension' },
  { value: DosageForm.INJECTION, label: 'Injection' },
  { value: DosageForm.OINTMENT, label: 'Ointment' },
  { value: DosageForm.CREAM, label: 'Cream' },
  { value: DosageForm.GEL, label: 'Gel' },
  { value: DosageForm.DROPS, label: 'Drops' },
  { value: DosageForm.POWDER, label: 'Powder' },
  { value: DosageForm.INHALER, label: 'Inhaler' },
  { value: DosageForm.OTHER, label: 'Other' },
];

export const DRUG_SCHEDULE_OPTIONS: Option<DrugSchedule>[] = [
  { value: DrugSchedule.NONE, label: 'None' },
  { value: DrugSchedule.H, label: 'Schedule H' },
  { value: DrugSchedule.H1, label: 'Schedule H1' },
  { value: DrugSchedule.X, label: 'Schedule X' },
];

function labeler<T extends string>(options: Option<T>[]): (value: T | null | undefined) => string {
  const map = new Map(options.map((o) => [o.value, o.label]));
  return (value) => (value == null ? '—' : (map.get(value) ?? value));
}

export const storageConditionLabel = labeler(STORAGE_CONDITION_OPTIONS);
export const materialClassificationLabel = labeler(MATERIAL_CLASSIFICATION_OPTIONS);
export const pharmacopoeiaLabel = labeler(PHARMACOPOEIA_OPTIONS);
export const dosageFormLabel = labeler(DOSAGE_FORM_OPTIONS);
export const drugScheduleLabel = labeler(DRUG_SCHEDULE_OPTIONS);
