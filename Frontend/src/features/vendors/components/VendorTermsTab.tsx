import { useState } from 'react';

import { useToast } from '@/components/toast/useToast';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { useItemsList } from '@/features/items/hooks/useItems';
import { useApiError } from '@/hooks/useApiError';
import { formatCurrency, formatDate } from '@/lib/format';
import type { VendorItemTerm } from '@/types/api.types';

import { useDeleteTerm } from '../hooks/useVendors';
import { VendorTermFormDrawer } from './VendorTermFormDrawer';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c'];

interface FormState {
  mode: 'create' | 'edit';
  term?: VendorItemTerm;
}

export interface VendorTermsTabProps {
  vendorId: string;
  terms: VendorItemTerm[];
  loading: boolean;
}

export function VendorTermsTab({ vendorId, terms, loading }: VendorTermsTabProps): JSX.Element {
  // Items power the picker + id→name resolution (reuses the items feature query).
  const itemsQuery = useItemsList({ limit: 100, offset: 0 });
  const items = itemsQuery.data?.items ?? [];
  const itemName = (id: string): string => {
    const item = items.find((i) => i.id === id);
    return item ? `${item.sku} — ${item.name}` : id;
  };

  const toast = useToast();
  const reportApiError = useApiError();
  const deleteMut = useDeleteTerm(vendorId);

  const [formState, setFormState] = useState<FormState | null>(null);
  const [removeTerm, setRemoveTerm] = useState<VendorItemTerm | null>(null);

  const confirmRemove = (): void => {
    if (!removeTerm) return;
    deleteMut.mutate(removeTerm.id, {
      onSuccess: () => {
        toast.success('Item unlinked.');
        setRemoveTerm(null);
      },
      onError: (error) => {
        reportApiError(error, { scope: 'vendors.term.delete', fallbackMessage: 'Could not remove the item.' });
        setRemoveTerm(null);
      },
    });
  };

  return (
    <Card>
      <CardHeader
        title="Items supplied"
        sub="Pricing terms for the items this vendor supplies"
        action={
          <Button variant="pri" size="sm" icon="plus" onClick={() => setFormState({ mode: 'create' })}>
            Link item
          </Button>
        }
      />

      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Item</th>
              <th className="right">Rate</th>
              <th className="right">Discount</th>
              <th>Effective from</th>
              <th>Effective to</th>
              <th className="right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              SKELETON_ROWS.map((key) => (
                <tr key={key}>
                  <td colSpan={COL_COUNT}>
                    <Skeleton height={16} />
                  </td>
                </tr>
              ))
            ) : terms.length === 0 ? (
              <tr>
                <td colSpan={COL_COUNT}>
                  <EmptyState
                    icon="box"
                    title="No linked items"
                    sub="Link an item to record this vendor's pricing for it."
                    action={
                      <Button variant="pri" icon="plus" onClick={() => setFormState({ mode: 'create' })}>
                        Link item
                      </Button>
                    }
                  />
                </td>
              </tr>
            ) : (
              terms.map((term) => (
                <tr key={term.id}>
                  <td>{itemName(term.item_id)}</td>
                  <td className="right mono">{formatCurrency(term.rate)}</td>
                  <td className="right mono">{term.discount_percent}%</td>
                  <td className="muted">{formatDate(term.effective_from)}</td>
                  <td className="muted">{term.effective_to ? formatDate(term.effective_to) : 'Open'}</td>
                  <td className="right">
                    <button
                      className="btn btn-txt btn-sm"
                      type="button"
                      onClick={() => setFormState({ mode: 'edit', term })}
                    >
                      Edit
                    </button>
                    <button className="btn btn-txt btn-sm" type="button" onClick={() => setRemoveTerm(term)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {formState && (
        <VendorTermFormDrawer
          vendorId={vendorId}
          mode={formState.mode}
          term={formState.term}
          items={items}
          onClose={() => setFormState(null)}
        />
      )}

      <Modal
        open={!!removeTerm}
        onClose={() => setRemoveTerm(null)}
        title="Remove linked item"
        sub={removeTerm ? itemName(removeTerm.item_id) : undefined}
        tone="danger"
        footer={
          <>
            <Button variant="sec" onClick={() => setRemoveTerm(null)}>
              Cancel
            </Button>
            <Button variant="dng" loading={deleteMut.isPending} onClick={confirmRemove}>
              Remove
            </Button>
          </>
        }
      >
        This unlinks the item's pricing terms from this vendor. You can re-add it later.
      </Modal>
    </Card>
  );
}
