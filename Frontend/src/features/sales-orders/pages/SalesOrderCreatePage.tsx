import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo } from 'react';
import { FormProvider, useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';

import { routes } from '@/app/routes';
import { useToast } from '@/components/toast/useToast';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { Textarea } from '@/components/ui/Textarea';
import { useCustomersList } from '@/features/customers/hooks/useCustomers';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';
import { formatCurrency } from '@/lib/format';
import type { Item } from '@/types/api.types';

import { SoLineItemsEditor } from '../components/SoLineItemsEditor';
import { useCreateSalesOrder } from '../hooks/useSalesOrders';
import { EMPTY_SO, soCreateSchema, type SoFormValues } from '../so.schema';
import { estimatedTotal, hasShortLine, toSoCreatePayload } from '../so.transform';

export function SalesOrderCreatePage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreateSalesOrder();
  const customersQuery = useCustomersList({ limit: 100, offset: 0 });
  const itemsQuery = useItemsList({ limit: 100, offset: 0, type: 'FINISHED' });
  const items = itemsQuery.data?.items ?? [];
  const itemMap = useMemo(
    () => new Map<string, Item>((itemsQuery.data?.items ?? []).map((i) => [i.id, i])),
    [itemsQuery.data],
  );

  const methods = useForm<SoFormValues>({ resolver: zodResolver(soCreateSchema), defaultValues: EMPTY_SO });
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = methods;

  const lines = watch('items');
  const total = estimatedTotal(lines);
  // §5 non-negotiable: block Create while any line orders more than is in stock.
  const anyShort = hasShortLine(lines, itemMap);

  const onValid = (values: SoFormValues): void => {
    createMut.mutate(toSoCreatePayload(values), {
      onSuccess: (so) => {
        toast.success(`${so.so_number} created.`);
        navigate(`${routes.salesOrders}/${so.id}`);
      },
      onError: (error) =>
        reportApiError(error, {
          scope: 'sales-orders.create',
          fallbackMessage: 'Could not create the sales order.',
        }),
    });
  };

  return (
    <FormProvider {...methods}>
      <PageHeader
        title="New Sales Order"
        sub="Stock is checked live — and committed when you ship"
        actions={
          <ButtonLink to={routes.salesOrders} variant="sec">
            ← Cancel
          </ButtonLink>
        }
      />

      <form onSubmit={handleSubmit(onValid)} noValidate>
        <Card pad>
          <div className="form-grid">
            <Field label="Customer" htmlFor="so-customer" required error={errors.customer_id?.message}>
              <Select id="so-customer" invalid={!!errors.customer_id} {...register('customer_id')}>
                <option value="">Select a customer…</option>
                {(customersQuery.data?.items ?? []).map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.company_name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Expected delivery"
              htmlFor="so-eta"
              error={errors.expected_delivery_date?.message}
            >
              <Input id="so-eta" type="date" {...register('expected_delivery_date')} />
            </Field>
            <div className="full">
              <Field label="Notes" htmlFor="so-notes" error={errors.notes?.message}>
                <Textarea id="so-notes" {...register('notes')} />
              </Field>
            </div>
          </div>
        </Card>

        <Card pad className="mt-16">
          <div className="sect-title">Line items</div>
          {itemsQuery.isPending ? (
            <Skeleton height={120} />
          ) : (
            <SoLineItemsEditor items={items} />
          )}
        </Card>

        <div className="sticky-foot">
          <div className="totals">
            <span className="l">Estimated total</span>
            <span className="v mono">{formatCurrency(total)}</span>
          </div>
          <div className="actions">
            {anyShort && (
              <span className="err">A line exceeds available stock — adjust quantities to continue.</span>
            )}
            <ButtonLink to={routes.salesOrders} variant="sec">
              Cancel
            </ButtonLink>
            <Button variant="pri" type="submit" loading={createMut.isPending} disabled={anyShort}>
              Create order
            </Button>
          </div>
        </div>
      </form>
    </FormProvider>
  );
}
