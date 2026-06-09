import { useQueryClient } from '@tanstack/react-query';

import { routes } from '@/app/routes';
import { useAuth } from '@/auth/useAuth';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button, ButtonLink } from '@/components/ui/Button';
import { formatLongDate } from '@/lib/format';

import { CrmSyncCard } from '../components/CrmSyncCard';
import { KpiRow } from '../components/KpiRow';
import { NeedsAttention } from '../components/NeedsAttention';
import { QuickActions } from '../components/QuickActions';
import { RecentMovements } from '../components/RecentMovements';
import { StockValueChart } from '../components/StockValueChart';
import { firstName, greeting } from '../dashboard.transform';
import { dashboardKeys } from '../hooks/useDashboard';
import '../dashboard.css';

export function DashboardPage(): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const now = new Date();
  const name = user ? firstName(user.full_name) : 'there';

  return (
    <>
      <PageHeader
        title={`${greeting(now.getHours())}, ${name}`}
        sub={`Here's what's moving across the plant today · ${formatLongDate(now)}`}
        actions={
          <>
            <Button
              variant="sec"
              icon="refresh"
              onClick={() => void queryClient.invalidateQueries({ queryKey: dashboardKeys.all })}
            >
              Refresh
            </Button>
            <ButtonLink to={routes.salesOrders} variant="pri" icon="plus">
              New Order
            </ButtonLink>
          </>
        }
      />

      <KpiRow />

      <div className="dash-grid">
        <div className="flex col gap-16">
          <StockValueChart />
          <RecentMovements />
        </div>
        <div className="flex col gap-16">
          <QuickActions />
          <NeedsAttention />
          <CrmSyncCard />
        </div>
      </div>
    </>
  );
}
