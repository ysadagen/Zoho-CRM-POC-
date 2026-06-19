import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { useAuth } from '@/auth/useAuth';
import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Drawer } from '@/components/ui/Drawer';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { useApiError } from '@/hooks/useApiError';
import { ApiError } from '@/lib/api/errors';
import type { Lead, LeadCreateRequest, LeadUpdateRequest } from '@/types/api.types';
import { DealerPotential, LeadSource } from '@/types/enums';

import { EMPTY_LEAD, leadSchema, type LeadValues } from '../lead.schema';
import { useCreateLead, useUpdateLead } from '../hooks/useLeads';

const FORM_FIELDS = new Set<keyof LeadValues>([
  'contact_name',
  'email',
  'phone',
  'estimated_budget',
  'required_by_date',
  'state',
  'district',
  'city',
  'pincode',
]);

function leadToValues(lead: Lead): LeadValues {
  return {
    contact_name: lead.contact_name,
    source: lead.source,
    phone: lead.phone ?? '',
    email: lead.email ?? '',
    estimated_budget: lead.estimated_budget ?? '',
    dealer_potential: lead.dealer_potential ?? '',
    required_by_date: lead.required_by_date ?? '',
    state: lead.state ?? '',
    district: lead.district ?? '',
    city: lead.city ?? '',
    pincode: lead.pincode ?? '',
    notes: lead.notes ?? '',
  };
}

/** Drop blank optional fields so the Backend sees omission, not empty strings. */
function toPayload(values: LeadValues): Omit<LeadCreateRequest, 'assigned_to_user_id'> {
  const opt = (v: string): string | undefined => (v.trim() === '' ? undefined : v.trim());
  return {
    contact_name: values.contact_name.trim(),
    source: values.source,
    phone: opt(values.phone),
    email: opt(values.email),
    estimated_budget: opt(values.estimated_budget),
    dealer_potential: values.dealer_potential === '' ? undefined : values.dealer_potential,
    required_by_date: opt(values.required_by_date),
    state: opt(values.state),
    district: opt(values.district),
    city: opt(values.city),
    pincode: opt(values.pincode),
    notes: opt(values.notes),
  };
}

export interface LeadFormDrawerProps {
  mode: 'create' | 'edit';
  lead?: Lead;
  onClose: () => void;
  onCreated?: (id: string) => void;
}

export function LeadFormDrawer({ mode, lead, onClose, onCreated }: LeadFormDrawerProps): JSX.Element {
  const isCreate = mode === 'create';
  const { user } = useAuth();
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateLead();
  const updateMut = useUpdateLead(lead?.id ?? '');

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LeadValues>({
    resolver: zodResolver(leadSchema),
    defaultValues: isCreate || !lead ? EMPTY_LEAD : leadToValues(lead),
  });

  const pending = createMut.isPending || updateMut.isPending;

  const routeError = (error: unknown, scope: string): void => {
    if (error instanceof ApiError && error.isValidation() && error.field) {
      const field = error.field as keyof LeadValues;
      if (FORM_FIELDS.has(field)) {
        setError(field, { message: error.message });
        return;
      }
    }
    reportApiError(error, { scope, fallbackMessage: 'Could not save the lead.' });
  };

  const onValid = (values: LeadValues): void => {
    const payload = toPayload(values);
    if (isCreate) {
      const body: LeadCreateRequest = {
        ...payload,
        assigned_to_user_id: user?.id ?? '',
      };
      createMut.mutate(body, {
        onSuccess: (created) => {
          toast.success(`Lead ${created.lead_number} added.`);
          onCreated?.(created.id);
          onClose();
        },
        onError: (error) => routeError(error, 'leads.create'),
      });
    } else {
      const body: LeadUpdateRequest = payload;
      updateMut.mutate(body, {
        onSuccess: (updated) => {
          toast.success(`Lead ${updated.lead_number} updated.`);
          onClose();
        },
        onError: (error) => routeError(error, 'leads.update'),
      });
    }
  };

  return (
    <Drawer open onClose={onClose} title={isCreate ? 'Add Lead' : 'Edit Lead'}>
      <form className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
        <Field label="Contact name" htmlFor="lead-name" required error={errors.contact_name?.message}>
          <Input id="lead-name" invalid={!!errors.contact_name} {...register('contact_name')} />
        </Field>
        <Field label="Source" htmlFor="lead-source" error={errors.source?.message}>
          <select id="lead-source" className="select" {...register('source')}>
            {Object.values(LeadSource).map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Phone" htmlFor="lead-phone" error={errors.phone?.message}>
          <Input id="lead-phone" {...register('phone')} />
        </Field>
        <Field label="Email" htmlFor="lead-email" error={errors.email?.message}>
          <Input id="lead-email" type="email" invalid={!!errors.email} {...register('email')} />
        </Field>
        <Field
          label="Estimated budget"
          htmlFor="lead-budget"
          error={errors.estimated_budget?.message}
        >
          <Input id="lead-budget" inputMode="decimal" {...register('estimated_budget')} />
        </Field>
        <Field label="Dealer potential" htmlFor="lead-potential">
          <select id="lead-potential" className="select" {...register('dealer_potential')}>
            <option value="">—</option>
            {Object.values(DealerPotential).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Required by" htmlFor="lead-required" error={errors.required_by_date?.message}>
          <Input id="lead-required" type="date" {...register('required_by_date')} />
        </Field>
        <Field label="State" htmlFor="lead-state">
          <Input id="lead-state" {...register('state')} />
        </Field>
        <Field label="District" htmlFor="lead-district">
          <Input id="lead-district" {...register('district')} />
        </Field>
        <Field label="City" htmlFor="lead-city">
          <Input id="lead-city" {...register('city')} />
        </Field>
        <Field label="Pincode" htmlFor="lead-pincode">
          <Input id="lead-pincode" {...register('pincode')} />
        </Field>

        <div className="drawer-foot">
          <Button variant="sec" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="pri" type="submit" loading={pending}>
            {isCreate ? 'Add lead' : 'Save changes'}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}
