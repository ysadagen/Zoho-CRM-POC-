import type { Customer, CustomerCreateRequest } from '@/types/api.types';

import type { CustomerValues } from './customer.schema';

/** Form → POST/PATCH body, dropping empty optionals (so we never send ""). */
export function toCustomerPayload(values: CustomerValues): CustomerCreateRequest {
  const payload: CustomerCreateRequest = {
    company_name: values.company_name,
    is_privileged: values.is_privileged,
    customer_type: values.customer_type,
    competitive_risk_level: values.competitive_risk_level,
  };
  if (values.contact_person) payload.contact_person = values.contact_person;
  if (values.email) payload.email = values.email;
  if (values.phone) payload.phone = values.phone;
  if (values.customer_code) payload.customer_code = values.customer_code;
  if (values.gstin) payload.gstin = values.gstin;
  if (values.address) payload.address = values.address;
  if (values.state) payload.state = values.state;
  if (values.city) payload.city = values.city;
  if (values.district) payload.district = values.district;
  if (values.pincode) payload.pincode = values.pincode;
  if (values.notes) payload.notes = values.notes;
  return payload;
}

/** Seeds the edit form from an existing customer (nulls → empty strings). */
export function customerToFormValues(customer: Customer): CustomerValues {
  return {
    company_name: customer.company_name,
    contact_person: customer.contact_person ?? '',
    email: customer.email ?? '',
    phone: customer.phone ?? '',
    customer_code: customer.customer_code ?? '',
    gstin: customer.gstin ?? '',
    is_privileged: customer.is_privileged,
    customer_type: customer.customer_type,
    competitive_risk_level: customer.competitive_risk_level,
    address: customer.address ?? '',
    state: customer.state ?? '',
    city: customer.city ?? '',
    district: customer.district ?? '',
    pincode: customer.pincode ?? '',
    notes: customer.notes ?? '',
  };
}
