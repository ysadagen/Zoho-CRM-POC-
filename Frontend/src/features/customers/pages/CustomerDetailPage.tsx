import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { Tabs } from '@/components/ui/Tabs';
import { ActivityTimeline } from '@/features/activities/components/ActivityTimeline';
import { LogActivityModal } from '@/features/activities/components/LogActivityModal';
import { formatDate } from '@/lib/format';
import type { Customer } from '@/types/api.types';

import { CustomerFormDrawer } from '../components/CustomerFormDrawer';
import { CustomerSalesOrdersTab } from '../components/CustomerSalesOrdersTab';
import { useCustomer, useCustomerSalesOrders } from '../hooks/useCustomers';

type DetailTab = 'profile' | 'orders' | 'activity';

const TABS = [
  { value: 'profile', label: 'Profile' },
  { value: 'orders', label: 'Sales orders' },
  { value: 'activity', label: 'Activity' },
] as const;

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }): JSX.Element {
  return (
    <div className="label-pair">
      <span className="l">{label}</span>
      <span className={mono ? 'v mono' : 'v'}>{value}</span>
    </div>
  );
}

function Profile({ customer }: { customer: Customer }): JSX.Element {
  return (
    <Card pad>
      <div className="grid-2 gap-24">
        <Detail label="Company name" value={customer.company_name} />
        <Detail label="Contact person" value={customer.contact_person ?? '—'} />
        <Detail label="Email" value={customer.email ?? '—'} />
        <Detail label="Phone" value={customer.phone ?? '—'} />
        <Detail label="Customer code" value={customer.customer_code ?? '—'} mono />
        <Detail label="GSTIN / Tax ID" value={customer.gstin ?? '—'} mono />
        <Detail label="Created" value={formatDate(customer.created_at)} />
        <Detail label="Last updated" value={formatDate(customer.updated_at)} />
      </div>
      {/* Zoho CRM sync is owned by the Integration Layer (a later phase). */}
      <div className="divider" />
      <div className="text-muted fs-12">Zoho CRM sync — not connected yet.</div>
    </Card>
  );
}

function DetailSkeleton(): JSX.Element {
  return (
    <>
      <div className="page-head">
        <Skeleton width={240} height={30} />
      </div>
      <Card pad>
        <Skeleton height={160} />
      </Card>
    </>
  );
}

export function CustomerDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const customerQuery = useCustomer(id);
  const ordersQuery = useCustomerSalesOrders(id);
  const [tab, setTab] = useState<DetailTab>('profile');
  const [editOpen, setEditOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);

  if (customerQuery.isPending) return <DetailSkeleton />;
  if (customerQuery.isError || !customerQuery.data) {
    return <PageError error={customerQuery.error} onRetry={() => void customerQuery.refetch()} />;
  }

  const customer = customerQuery.data;

  return (
    <>
      <PageHeader
        title={customer.company_name}
        sub={
          <span className="flex items-center gap-8">
            {customer.customer_code && <span className="mono">{customer.customer_code}</span>}
            {customer.is_privileged && <Badge variant="warn">Privileged</Badge>}
          </span>
        }
        actions={
          <>
            <ButtonLink to={routes.customers} variant="sec">
              ← Customers
            </ButtonLink>
            <Button variant="pri" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
          </>
        }
      />

      <Tabs tabs={[...TABS]} value={tab} onChange={setTab} ariaLabel="Customer detail sections" />

      {tab === 'profile' && <Profile customer={customer} />}
      {tab === 'orders' && (
        <CustomerSalesOrdersTab
          orders={ordersQuery.data?.items ?? []}
          loading={ordersQuery.isPending}
        />
      )}
      {tab === 'activity' && (
        <Card pad>
          <CardHeader
            title="Activity"
            action={
              <Button variant="sec" icon="plus" onClick={() => setLogOpen(true)}>
                Log activity
              </Button>
            }
          />
          <ActivityTimeline customerId={id} />
        </Card>
      )}

      {editOpen && (
        <CustomerFormDrawer mode="edit" customer={customer} onClose={() => setEditOpen(false)} />
      )}
      {logOpen && <LogActivityModal customerId={id} onClose={() => setLogOpen(false)} />}
    </>
  );
}
