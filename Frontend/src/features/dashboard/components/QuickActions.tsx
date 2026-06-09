import { Link } from 'react-router-dom';

import { routes } from '@/app/routes';
import { Card } from '@/components/ui/Card';
import { Icon, type IconName } from '@/components/ui/Icon';

interface QuickAction {
  to: string;
  icon: IconName;
  label: string;
  sub: string;
}

const ACTIONS: QuickAction[] = [
  { to: routes.items, icon: 'package', label: 'Add Item', sub: 'Raw or finished' },
  { to: routes.purchaseOrders, icon: 'cart', label: 'New Purchase Order', sub: 'From a vendor' },
  { to: routes.salesOrders, icon: 'bag', label: 'New Sales Order', sub: 'To a customer' },
  { to: routes.customers, icon: 'user', label: 'Add Customer', sub: 'Auto-syncs to Zoho' },
];

export function QuickActions(): JSX.Element {
  return (
    <Card pad>
      <div className="eyebrow mb-16">Quick Actions</div>
      <div className="qa-grid">
        {ACTIONS.map((action) => (
          <Link key={action.label} className="qa" to={action.to}>
            <span className="ic">
              <Icon name={action.icon} />
            </span>
            <div>
              <div className="l">{action.label}</div>
              <div className="s">{action.sub}</div>
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}
