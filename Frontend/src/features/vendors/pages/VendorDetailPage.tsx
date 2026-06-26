import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { routes } from '@/app/routes';
import { PageError } from '@/components/errors/PageError';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { Tabs } from '@/components/ui/Tabs';
import { formatDate } from '@/lib/format';
import type { Vendor } from '@/types/api.types';

import { VendorFormDrawer } from '../components/VendorFormDrawer';
import { VendorPurchaseOrdersTab } from '../components/VendorPurchaseOrdersTab';
import { VendorTermsTab } from '../components/VendorTermsTab';
import { useVendor, useVendorPurchaseOrders, useVendorTerms } from '../hooks/useVendors';

type DetailTab = 'profile' | 'items' | 'orders';

const TABS = [
  { value: 'profile', label: 'Profile' },
  { value: 'items', label: 'Items supplied' },
  { value: 'orders', label: 'Purchase orders' },
] as const;

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }): JSX.Element {
  return (
    <div className="label-pair">
      <span className="l">{label}</span>
      <span className={mono ? 'v mono' : 'v'}>{value}</span>
    </div>
  );
}

function Profile({ vendor }: { vendor: Vendor }): JSX.Element {
  return (
    <Card pad>
      <div className="grid-2 gap-24">
        <Detail label="Vendor name" value={vendor.vendor_name} />
        <Detail label="Contact person" value={vendor.contact_person ?? '—'} />
        <Detail label="Email" value={vendor.email ?? '—'} />
        <Detail label="Phone" value={vendor.phone ?? '—'} />
        <Detail label="Vendor code" value={vendor.vendor_code ?? '—'} mono />
        <Detail label="GSTIN / Tax ID" value={vendor.gstin ?? '—'} mono />
        <Detail label="Created" value={formatDate(vendor.created_at)} />
        <Detail label="Last updated" value={formatDate(vendor.updated_at)} />
      </div>
      {vendor.address && (
        <>
          <div className="divider" />
          <div className="grid-2 gap-24">
            <Detail label="Address" value={vendor.address} />
          </div>
        </>
      )}
      {vendor.notes && (
        <>
          <div className="divider" />
          <div className="grid-2 gap-24">
            <Detail label="Notes" value={vendor.notes} />
          </div>
        </>
      )}
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

export function VendorDetailPage(): JSX.Element {
  const { id = '' } = useParams();
  const vendorQuery = useVendor(id);
  const termsQuery = useVendorTerms(id);
  const ordersQuery = useVendorPurchaseOrders(id);
  const [tab, setTab] = useState<DetailTab>('profile');
  const [editOpen, setEditOpen] = useState(false);

  if (vendorQuery.isPending) return <DetailSkeleton />;
  if (vendorQuery.isError || !vendorQuery.data) {
    return <PageError error={vendorQuery.error} onRetry={() => void vendorQuery.refetch()} />;
  }

  const vendor = vendorQuery.data;

  return (
    <>
      <PageHeader
        title={vendor.vendor_name}
        sub={vendor.vendor_code ? <span className="mono">{vendor.vendor_code}</span> : undefined}
        actions={
          <>
            <ButtonLink to={routes.vendors} variant="sec">
              ← Vendors
            </ButtonLink>
            <Button variant="pri" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
          </>
        }
      />

      <Tabs tabs={[...TABS]} value={tab} onChange={setTab} ariaLabel="Vendor detail sections" />

      {tab === 'profile' && <Profile vendor={vendor} />}
      {tab === 'items' && (
        <VendorTermsTab
          vendorId={vendor.id}
          terms={termsQuery.data?.items ?? []}
          loading={termsQuery.isPending}
        />
      )}
      {tab === 'orders' && (
        <VendorPurchaseOrdersTab
          orders={ordersQuery.data?.items ?? []}
          loading={ordersQuery.isPending}
        />
      )}

      {editOpen && (
        <VendorFormDrawer mode="edit" vendor={vendor} onClose={() => setEditOpen(false)} />
      )}
    </>
  );
}
