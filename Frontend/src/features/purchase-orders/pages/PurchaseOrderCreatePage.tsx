import { zodResolver } from '@hookform/resolvers/zod';
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
import { useItemsList } from '@/features/items/hooks/useItems';
import { useVendorsList } from '@/features/vendors/hooks/useVendors';
import { useApiError } from '@/hooks/useApiError';
import { formatCurrency } from '@/lib/format';

import { PoLineItemsEditor } from '../components/PoLineItemsEditor';
import { useCreatePurchaseOrder } from '../hooks/usePurchaseOrders';
import { EMPTY_PO, poCreateSchema, type PoFormValues } from '../po.schema';
import { estimatedTotal, toPoCreatePayload } from '../po.transform';

export function PurchaseOrderCreatePage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const reportApiError = useApiError();
  const createMut = useCreatePurchaseOrder();
  const vendorsQuery = useVendorsList({ limit: 100, offset: 0 });
  const itemsQuery = useItemsList({ limit: 100, offset: 0, type: 'RAW' });

  const methods = useForm<PoFormValues>({ resolver: zodResolver(poCreateSchema), defaultValues: EMPTY_PO });
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = methods;

  const total = estimatedTotal(watch('items'));

  const onValid = (values: PoFormValues): void => {
    createMut.mutate(toPoCreatePayload(values), {
      onSuccess: (po) => {
        toast.success(`${po.po_number} created.`);
        navigate(`${routes.purchaseOrders}/${po.id}`);
      },
      onError: (error) =>
        reportApiError(error, {
          scope: 'purchase-orders.create',
          fallbackMessage: 'Could not create the purchase order.',
        }),
    });
  };

  return (
    <FormProvider {...methods}>
      <PageHeader
        title="New Purchase Order"
        sub="Saved as a draft — stock changes only when you receive it"
        actions={
          <ButtonLink to={routes.purchaseOrders} variant="sec">
            ← Cancel
          </ButtonLink>
        }
      />

      <form onSubmit={handleSubmit(onValid)} noValidate>
        <Card pad>
          <div className="form-grid">
            <Field label="Vendor" htmlFor="po-vendor" required error={errors.vendor_id?.message}>
              <Select id="po-vendor" invalid={!!errors.vendor_id} {...register('vendor_id')}>
                <option value="">Select a vendor…</option>
                {(vendorsQuery.data?.items ?? []).map((vendor) => (
                  <option key={vendor.id} value={vendor.id}>
                    {vendor.vendor_name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Expected delivery"
              htmlFor="po-eta"
              error={errors.expected_delivery_date?.message}
            >
              <Input id="po-eta" type="date" {...register('expected_delivery_date')} />
            </Field>
            <div className="full">
              <Field label="Notes" htmlFor="po-notes" error={errors.notes?.message}>
                <Textarea id="po-notes" {...register('notes')} />
              </Field>
            </div>
          </div>
        </Card>

        <Card pad className="mt-16">
          <div className="sect-title">Line items</div>
          {itemsQuery.isPending ? (
            <Skeleton height={120} />
          ) : (
            <PoLineItemsEditor items={itemsQuery.data?.items ?? []} />
          )}
        </Card>

        <div className="sticky-foot">
          <div className="totals">
            <span className="l">Estimated total</span>
            <span className="v mono">{formatCurrency(total)}</span>
          </div>
          <div className="actions">
            <ButtonLink to={routes.purchaseOrders} variant="sec">
              Cancel
            </ButtonLink>
            <Button variant="pri" type="submit" loading={createMut.isPending}>
              Save as Draft
            </Button>
          </div>
        </div>
      </form>
    </FormProvider>
  );
}
