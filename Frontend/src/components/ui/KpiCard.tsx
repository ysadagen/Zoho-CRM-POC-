import { cx } from '@/lib/cx';

import { Icon, type IconName } from './Icon';

export type KpiTone = 'default' | 'accent' | 'danger' | 'success' | 'info';

export interface KpiCardProps {
  tone?: KpiTone;
  icon: IconName;
  label: string;
  value: string;
  /** Delta line text, e.g. "▲ 12.5% vs last month". */
  delta?: string;
  /** Colours the delta line (independent of the arrow in the text). */
  deltaDir?: 'up' | 'down';
}

export function KpiCard({
  tone = 'default',
  icon,
  label,
  value,
  delta,
  deltaDir,
}: KpiCardProps): JSX.Element {
  return (
    <div className={cx('kpi', tone !== 'default' && tone)}>
      <div className="icon-pill">
        <Icon name={icon} size={14} />
      </div>
      <div className="label">{label}</div>
      <div className="val">{value}</div>
      {delta && <div className={cx('delta', deltaDir)}>{delta}</div>}
    </div>
  );
}
