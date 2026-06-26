import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useApiError } from '@/hooks/useApiError';
import { ApiError } from '@/lib/api/errors';
import type { Vendor } from '@/types/api.types';

import { useCreateVendor, useUpdateVendor } from '../hooks/useVendors';
import { EMPTY_VENDOR, vendorSchema, type VendorValues } from '../vendor.schema';
import { toVendorPayload, vendorToFormValues } from '../vendor.transform';

const FORM_ID = 'vendor-form';

const FORM_FIELDS = new Set<keyof VendorValues>([
  'vendor_name',
  'contact_person',
  'email',
  'phone',
  'vendor_code',
  'gstin',
  'address',
  'notes',
]);

export interface VendorFormDrawerProps {
  mode: 'create' | 'edit';
  vendor?: Vendor;
  onClose: () => void;
  onCreated?: (id: string) => void;
}

export function VendorFormDrawer({ mode, vendor, onClose, onCreated }: VendorFormDrawerProps): JSX.Element {
  const isCreate = mode === 'create';
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateVendor();
  const updateMut = useUpdateVendor(vendor?.id ?? '');

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<VendorValues>({
    resolver: zodResolver(vendorSchema),
    defaultValues: isCreate || !vendor ? EMPTY_VENDOR : vendorToFormValues(vendor),
  });

  const pending = createMut.isPending || updateMut.isPending;

  const routeError = (error: unknown, scope: string): void => {
    if (error instanceof ApiError && error.isValidation() && error.field) {
      const field = error.field as keyof VendorValues;
      if (FORM_FIELDS.has(field)) {
        setError(field, { message: error.message });
        return;
      }
    }
    reportApiError(error, { scope, fallbackMessage: 'Could not save the vendor.' });
  };

  const onValid = (values: VendorValues): void => {
    const payload = toVendorPayload(values);
    if (isCreate) {
      createMut.mutate(payload, {
        onSuccess: (created) => {
          toast.success(`${created.vendor_name} added.`);
          onCreated?.(created.id);
          onClose();
        },
        onError: (error) => routeError(error, 'vendors.create'),
      });
    } else {
      updateMut.mutate(payload, {
        onSuccess: (updated) => {
          toast.success(`${updated.vendor_name} updated.`);
          onClose();
        },
        onError: (error) => routeError(error, 'vendors.update'),
      });
    }
  };

  return (
    <Drawer open onClose={onClose} title={isCreate ? 'Add Vendor' : 'Edit Vendor'}>
      <form id={FORM_ID} className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Vendor name" htmlFor="vnd-name" required error={errors.vendor_name?.message}>
          <Input id="vnd-name" invalid={!!errors.vendor_name} {...register('vendor_name')} />
        </Field>
        <Field label="Contact person" htmlFor="vnd-contact" error={errors.contact_person?.message}>
          <Input id="vnd-contact" {...register('contact_person')} />
        </Field>
        <Field label="Email" htmlFor="vnd-email" error={errors.email?.message}>
          <Input id="vnd-email" type="email" invalid={!!errors.email} {...register('email')} />
        </Field>
        <Field label="Phone" htmlFor="vnd-phone" error={errors.phone?.message}>
          <Input id="vnd-phone" {...register('phone')} />
        </Field>
        <Field label="Vendor code" htmlFor="vnd-code" error={errors.vendor_code?.message}>
          <Input id="vnd-code" {...register('vendor_code')} />
        </Field>
        <Field label="GSTIN / Tax ID" htmlFor="vnd-gstin" error={errors.gstin?.message}>
          <Input id="vnd-gstin" {...register('gstin')} />
        </Field>

        <div className="divider" />
        <div className="sect-title">Additional info</div>
        <Field label="Address" htmlFor="vnd-address" error={errors.address?.message}>
          <Textarea id="vnd-address" invalid={!!errors.address} rows={3} {...register('address')} />
        </Field>
        <Field label="Notes" htmlFor="vnd-notes" error={errors.notes?.message}>
          <Textarea id="vnd-notes" invalid={!!errors.notes} rows={3} {...register('notes')} />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={pending}>
            {isCreate ? 'Add vendor' : 'Save changes'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
