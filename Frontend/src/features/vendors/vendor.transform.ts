import type {
  Vendor,
  VendorCreateRequest,
  VendorItemTerm,
  VendorItemTermCreateRequest,
  VendorItemTermUpdateRequest,
} from '@/types/api.types';

import type { VendorTermValues, VendorValues } from './vendor.schema';

export function toVendorPayload(values: VendorValues): VendorCreateRequest {
  const payload: VendorCreateRequest = { vendor_name: values.vendor_name };
  if (values.contact_person) payload.contact_person = values.contact_person;
  if (values.email) payload.email = values.email;
  if (values.phone) payload.phone = values.phone;
  if (values.vendor_code) payload.vendor_code = values.vendor_code;
  if (values.gstin) payload.gstin = values.gstin;
  if (values.address) payload.address = values.address;
  if (values.notes) payload.notes = values.notes;
  return payload;
}

export function vendorToFormValues(vendor: Vendor): VendorValues {
  return {
    vendor_name: vendor.vendor_name,
    contact_person: vendor.contact_person ?? '',
    email: vendor.email ?? '',
    phone: vendor.phone ?? '',
    vendor_code: vendor.vendor_code ?? '',
    gstin: vendor.gstin ?? '',
    address: vendor.address ?? '',
    notes: vendor.notes ?? '',
  };
}

/** Form → POST term body (drops empty optionals). */
export function toTermCreatePayload(values: VendorTermValues): VendorItemTermCreateRequest {
  const payload: VendorItemTermCreateRequest = {
    item_id: values.item_id,
    rate: values.rate,
    effective_from: values.effective_from,
  };
  if (values.discount_percent) payload.discount_percent = values.discount_percent;
  if (values.effective_to) payload.effective_to = values.effective_to;
  return payload;
}

/** Form → PATCH term body (item_id is immutable on a term). */
export function toTermUpdatePayload(values: VendorTermValues): VendorItemTermUpdateRequest {
  return {
    rate: values.rate,
    discount_percent: values.discount_percent || '0',
    effective_from: values.effective_from,
    effective_to: values.effective_to ? values.effective_to : null,
  };
}

export function termToFormValues(term: VendorItemTerm): VendorTermValues {
  return {
    item_id: term.item_id,
    rate: term.rate,
    discount_percent: term.discount_percent,
    effective_from: term.effective_from,
    effective_to: term.effective_to ?? '',
  };
}
