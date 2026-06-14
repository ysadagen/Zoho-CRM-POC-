import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDate } from '@/lib/format';
import type { Customer } from '@/types/api.types';

const COL_COUNT = 6;
const SKELETON_ROWS = ['a', 'b', 'c', 'd', 'e'];

export interface CustomersTableProps {
  customers: Customer[];
  loading: boolean;
  onEdit: (customer: Customer) => void;
  onAdd: () => void;
}

export function CustomersTable({ customers, loading, onEdit, onAdd }: CustomersTableProps): JSX.Element {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Company</th>
            <th>Contact</th>
            <th>Email</th>
            <th>Phone</th>
            <th>Created</th>
            <th className="right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            SKELETON_ROWS.map((key) => (
              <tr key={key}>
                <td colSpan={COL_COUNT}>
                  <Skeleton height={18} />
                </td>
              </tr>
            ))
          ) : customers.length === 0 ? (
            <tr>
              <td colSpan={COL_COUNT}>
                <EmptyState
                  icon="user"
                  title="No customers found"
                  sub="Try a different search, or add your first customer."
                  action={
                    <Button variant="pri" icon="plus" onClick={onAdd}>
                      Add Customer
                    </Button>
                  }
                />
              </td>
            </tr>
          ) : (
            customers.map((customer) => (
              <tr key={customer.id}>
                <td>
                  <span className="flex items-center gap-8">
                    <Link className="tbl-link" to={`${routes.customers}/${customer.id}`}>
                      {customer.company_name}
                    </Link>
                    {customer.is_privileged && <Badge variant="warn">Privileged</Badge>}
                  </span>
                </td>
                <td className="muted">{customer.contact_person ?? '—'}</td>
                <td className="muted">{customer.email ?? '—'}</td>
                <td className="muted">{customer.phone ?? '—'}</td>
                <td className="muted">{formatDate(customer.created_at)}</td>
                <td className="right">
                  <Link className="btn btn-txt btn-sm" to={`${routes.customers}/${customer.id}`}>
                    View
                  </Link>
                  <button className="btn btn-txt btn-sm" type="button" onClick={() => onEdit(customer)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
