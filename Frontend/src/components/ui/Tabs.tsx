import { cx } from '@/lib/cx';

export interface TabItem<T extends string> {
  value: T;
  label: string;
}

export interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel?: string;
}

/** Underlined tab row for detail pages (DESIGN_SYSTEM §6.12). */
export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  ariaLabel,
}: TabsProps<T>): JSX.Element {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={tab.value === value}
          className={cx('tab', tab.value === value && 'active')}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
