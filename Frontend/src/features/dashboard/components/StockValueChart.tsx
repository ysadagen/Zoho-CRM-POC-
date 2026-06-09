import { useState } from 'react';

import { Card } from '@/components/ui/Card';
import { Segmented, type SegmentedOption } from '@/components/ui/Segmented';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatCurrency } from '@/lib/format';

import { totalStockValue } from '../dashboard.transform';
import { useDashboardItems } from '../hooks/useDashboard';

type ChartRange = '7D' | '30D' | '90D' | 'YTD';

const RANGES: SegmentedOption<ChartRange>[] = [
  { value: '7D', label: '7D' },
  { value: '30D', label: '30D' },
  { value: '90D', label: '90D' },
  { value: 'YTD', label: 'YTD' },
];

// Static series ported from the mock. Replaced by a computed series when the
// dashboard is wired to /stock-movements (later phase).
const AREA_PATH =
  'M0,135 L 30,128 60,118 100,124 140,110 180,100 220,108 260,92 300,98 340,82 380,90 420,72 460,80 500,66 540,58 580,72 620,52 660,60 700,42 740,50 780,34 800,40 L 800,180 L 0,180 Z';
const LINE_PATH =
  'M0,135 L 30,128 60,118 100,124 140,110 180,100 220,108 260,92 300,98 340,82 380,90 420,72 460,80 500,66 540,58 580,72 620,52 660,60 700,42 740,50 780,34 800,40';
const RAW_PATH =
  'M0,150 L 60,148 140,142 220,140 300,134 380,130 460,124 540,118 620,112 700,104 780,98 800,96';

export function StockValueChart(): JSX.Element {
  const [range, setRange] = useState<ChartRange>('30D');
  const items = useDashboardItems();

  return (
    <Card>
      <div className="chart-wrap">
        <div className="chart-head">
          <div>
            <div className="eyebrow">Total Stock Value</div>
            <div className="figure">
              {items.data === undefined ? (
                <Skeleton width={200} height={30} />
              ) : (
                <span className="big">{formatCurrency(totalStockValue(items.data))}</span>
              )}
            </div>
          </div>
          {/* Range toggle is retained for the design; a historical series lands
              with the reporting phase, so the trend below is illustrative. */}
          <Segmented
            options={RANGES}
            value={range}
            onChange={setRange}
            ariaLabel="Stock value time range"
          />
        </div>

        <svg className="area-chart" viewBox="0 0 800 180" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="dash-chart-grad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#eeaa42" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#eeaa42" stopOpacity="0" />
            </linearGradient>
          </defs>
          <g stroke="#e3e4dc" strokeWidth="1">
            <line x1="0" y1="40" x2="800" y2="40" />
            <line x1="0" y1="90" x2="800" y2="90" />
            <line x1="0" y1="140" x2="800" y2="140" />
          </g>
          <path d={AREA_PATH} fill="url(#dash-chart-grad)" />
          <path
            d={LINE_PATH}
            fill="none"
            stroke="#eeaa42"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d={RAW_PATH}
            fill="none"
            stroke="#bd4d35"
            strokeWidth="2"
            strokeDasharray="3 3"
            strokeLinecap="round"
          />
          <circle cx="800" cy="40" r="5" fill="#fff" stroke="#eeaa42" strokeWidth="2.5" />
        </svg>

        <div className="legend">
          <span>
            <span className="sw sw-finished" />
            Finished Products
          </span>
          <span>
            <span className="sw sw-raw" />
            Raw Materials
          </span>
          <span className="updated">Trend illustrative</span>
        </div>
      </div>
    </Card>
  );
}
