import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { useApiError } from '@/hooks/useApiError';
import { formatDate } from '@/lib/format';
import type { CustomerTarget } from '@/types/api.types';

import { useCreateCustomerTarget, useCustomerTargets } from '../hooks/useCustomers';

const DECIMAL_RE = /^\d+(\.\d+)?$/;

const targetSchema = z.object({
  period_start: z.string().min(1, 'Start date is required'),
  period_end: z.string().min(1, 'End date is required'),
  target_quantity: z
    .string()
    .trim()
    .min(1, 'Quantity is required')
    .refine((v) => DECIMAL_RE.test(v), 'Must be a non-negative number'),
  target_revenue: z
    .string()
    .trim()
    .refine((v) => v === '' || DECIMAL_RE.test(v), 'Must be a non-negative number'),
});

type TargetValues = z.infer<typeof targetSchema>;

const EMPTY_TARGET: TargetValues = {
  period_start: '',
  period_end: '',
  target_quantity: '',
  target_revenue: '',
};

const SKELETON_ROWS = ['a', 'b', 'c'];
const COL_COUNT = 4;

function TargetTable({ targets }: { targets: CustomerTarget[] }): JSX.Element {
  if (targets.length === 0) {
    return (
      <EmptyState
        icon="check"
        title="No targets yet"
        sub="Add a target period to track performance against goals."
      />
    );
  }

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Period start</th>
            <th>Period end</th>
            <th className="right">Target quantity</th>
            <th className="right">Target revenue</th>
          </tr>
        </thead>
        <tbody>
          {targets.map((t) => (
            <tr key={t.id}>
              <td className="muted">{formatDate(t.period_start)}</td>
              <td className="muted">{formatDate(t.period_end)}</td>
              <td className="right mono">{t.target_quantity}</td>
              <td className="right mono">{t.target_revenue ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface AddTargetFormProps {
  customerId: string;
  onDone: () => void;
}

function AddTargetForm({ customerId, onDone }: AddTargetFormProps): JSX.Element {
  const createMut = useCreateCustomerTarget(customerId);
  const reportApiError = useApiError();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<TargetValues>({
    resolver: zodResolver(targetSchema),
    defaultValues: EMPTY_TARGET,
  });

  const onValid = (values: TargetValues): void => {
    const body = {
      period_start: values.period_start,
      period_end: values.period_end,
      target_quantity: values.target_quantity,
      ...(values.target_revenue ? { target_revenue: values.target_revenue } : {}),
    };
    createMut.mutate(body, {
      onSuccess: onDone,
      onError: (error) =>
        reportApiError(error, { scope: 'customer_targets.create', fallbackMessage: 'Could not save target.' }),
    });
  };

  return (
    <form className="flex col gap-16" onSubmit={handleSubmit(onValid)} noValidate>
      <div className="form-grid">
        <Field label="Period start" htmlFor="tgt-start" required error={errors.period_start?.message}>
          <Input id="tgt-start" type="date" invalid={!!errors.period_start} {...register('period_start')} />
        </Field>
        <Field label="Period end" htmlFor="tgt-end" required error={errors.period_end?.message}>
          <Input id="tgt-end" type="date" invalid={!!errors.period_end} {...register('period_end')} />
        </Field>
        <Field label="Target quantity" htmlFor="tgt-qty" required error={errors.target_quantity?.message}>
          <Input id="tgt-qty" type="number" min="0" step="any" invalid={!!errors.target_quantity} {...register('target_quantity')} />
        </Field>
        <Field label="Target revenue (optional)" htmlFor="tgt-rev" error={errors.target_revenue?.message}>
          <Input id="tgt-rev" type="number" min="0" step="any" invalid={!!errors.target_revenue} {...register('target_revenue')} />
        </Field>
      </div>
      <div className="flex gap-8">
        <Button variant="sec" type="button" onClick={onDone}>
          Cancel
        </Button>
        <Button variant="pri" type="submit" loading={createMut.isPending}>
          Save target
        </Button>
      </div>
    </form>
  );
}

export interface CustomerTargetsTabProps {
  customerId: string;
}

export function CustomerTargetsTab({ customerId }: CustomerTargetsTabProps): JSX.Element {
  const [addOpen, setAddOpen] = useState(false);
  const targetsQuery = useCustomerTargets(customerId);

  if (targetsQuery.isPending) {
    return (
      <Card pad>
        <table className="tbl">
          <tbody>
            {SKELETON_ROWS.map((key) => (
              <tr key={key}>
                <td colSpan={COL_COUNT}>
                  <Skeleton height={16} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    );
  }

  const targets = targetsQuery.data ?? [];

  return (
    <Card pad>
      <CardHeader
        title="Sales targets"
        action={
          !addOpen ? (
            <Button variant="sec" icon="plus" onClick={() => setAddOpen(true)}>
              Add target
            </Button>
          ) : null
        }
      />
      {addOpen && (
        <>
          <AddTargetForm customerId={customerId} onDone={() => setAddOpen(false)} />
          <div className="divider" />
        </>
      )}
      <TargetTable targets={targets} />
    </Card>
  );
}
