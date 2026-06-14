import { describe, it, expect } from 'vitest';

import type { Customer } from '@/types/api.types';

import { customerToFormValues, toCustomerPayload } from './customer.transform';
import { EMPTY_CUSTOMER } from './customer.schema';

function customer(overrides: Partial<Customer> = {}): Customer {
  return {
    id: 'c1',
    company_name: 'Acme',
    contact_person: 'Anita',
    email: 'ops@acme.test',
    phone: '+91 90000 00000',
    customer_code: 'ACME-1',
    gstin: 'GST123',
    is_privileged: true,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

describe('toCustomerPayload', () => {
  it('keeps required fields and drops empty optionals', () => {
    expect(toCustomerPayload({ ...EMPTY_CUSTOMER, company_name: 'Acme', is_privileged: true })).toEqual({
      company_name: 'Acme',
      is_privileged: true,
    });
  });

  it('carries filled optionals through', () => {
    const payload = toCustomerPayload({
      company_name: 'Acme',
      contact_person: 'Anita',
      email: 'ops@acme.test',
      phone: '123',
      customer_code: 'ACME-1',
      gstin: 'GST123',
      is_privileged: false,
    });
    expect(payload).toMatchObject({
      contact_person: 'Anita',
      email: 'ops@acme.test',
      customer_code: 'ACME-1',
      gstin: 'GST123',
    });
  });
});

describe('customerToFormValues', () => {
  it('coerces nulls to empty strings', () => {
    expect(
      customerToFormValues(customer({ contact_person: null, email: null, gstin: null, customer_code: null, phone: null })),
    ).toEqual({
      company_name: 'Acme',
      contact_person: '',
      email: '',
      phone: '',
      customer_code: '',
      gstin: '',
      is_privileged: true,
    });
  });
});
