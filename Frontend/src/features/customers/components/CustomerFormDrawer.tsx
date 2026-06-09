import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { useApiError } from '@/hooks/useApiError';
import { ApiError } from '@/lib/api/errors';
import type { Customer } from '@/types/api.types';

import { useCreateCustomer, useUpdateCustomer } from '../hooks/useCustomers';
import { EMPTY_CUSTOMER, customerSchema, type CustomerValues } from '../customer.schema';
import { customerToFormValues, toCustomerPayload } from '../customer.transform';

const FORM_ID = 'customer-form';

const FORM_FIELDS = new Set<keyof CustomerValues>([
  'company_name',
  'contact_person',
  'email',
  'phone',
  'customer_code',
  'gstin',
]);

export interface CustomerFormDrawerProps {
  mode: 'create' | 'edit';
  customer?: Customer;
  onClose: () => void;
  onCreated?: (id: string) => void;
}

export function CustomerFormDrawer({
  mode,
  customer,
  onClose,
  onCreated,
}: CustomerFormDrawerProps): JSX.Element {
  const isCreate = mode === 'create';
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateCustomer();
  const updateMut = useUpdateCustomer(customer?.id ?? '');

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<CustomerValues>({
    resolver: zodResolver(customerSchema),
    defaultValues: isCreate || !customer ? EMPTY_CUSTOMER : customerToFormValues(customer),
  });

  const pending = createMut.isPending || updateMut.isPending;

  const routeError = (error: unknown, scope: string): void => {
    if (error instanceof ApiError && error.isValidation() && error.field) {
      const field = error.field as keyof CustomerValues;
      if (FORM_FIELDS.has(field)) {
        setError(field, { message: error.message });
        return;
      }
    }
    reportApiError(error, { scope, fallbackMessage: 'Could not save the customer.' });
  };

  const onValid = (values: CustomerValues): void => {
    const payload = toCustomerPayload(values);
    if (isCreate) {
      createMut.mutate(payload, {
        onSuccess: (created) => {
          toast.success(`${created.company_name} added.`);
          onCreated?.(created.id);
          onClose();
        },
        onError: (error) => routeError(error, 'customers.create'),
      });
    } else {
      updateMut.mutate(payload, {
        onSuccess: (updated) => {
          toast.success(`${updated.company_name} updated.`);
          onClose();
        },
        onError: (error) => routeError(error, 'customers.update'),
      });
    }
  };

  return (
    <Drawer open onClose={onClose} title={isCreate ? 'Add Customer' : 'Edit Customer'}>
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Company name" htmlFor="cust-name" required error={errors.company_name?.message}>
          <Input id="cust-name" invalid={!!errors.company_name} {...register('company_name')} />
        </Field>
        <Field label="Contact person" htmlFor="cust-contact" error={errors.contact_person?.message}>
          <Input id="cust-contact" {...register('contact_person')} />
        </Field>
        <Field label="Email" htmlFor="cust-email" error={errors.email?.message}>
          <Input id="cust-email" type="email" invalid={!!errors.email} {...register('email')} />
        </Field>
        <Field label="Phone" htmlFor="cust-phone" error={errors.phone?.message}>
          <Input id="cust-phone" {...register('phone')} />
        </Field>
        <Field label="Customer code" htmlFor="cust-code" error={errors.customer_code?.message}>
          <Input id="cust-code" {...register('customer_code')} />
        </Field>
        <Field label="GSTIN / Tax ID" htmlFor="cust-gstin" error={errors.gstin?.message}>
          <Input id="cust-gstin" {...register('gstin')} />
        </Field>
        <label className="check-row">
          <input type="checkbox" {...register('is_privileged')} />
          Privileged customer
        </label>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={pending}>
            {isCreate ? 'Add customer' : 'Save changes'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
