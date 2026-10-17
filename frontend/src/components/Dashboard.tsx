import React from 'react';
import { TitleBar } from './layout/TitleBar';
import { TickerBar } from './layout/TickerBar';
import { IndicatorCard } from './cards/IndicatorCard';
import { KPISubCard } from './cards/KPISubCard';
import { ChartLegend } from './cards/ChartLegend';
import { GroupedBarChart } from './charts/GroupedBarChart';
import { AreaLineChart } from './charts/AreaLineChart';
import { MixedBarLineChart } from './charts/MixedBarLineChart';
import { toFixed } from '../utils/format';
import type { Dashboard as DashboardData, Indicator, Point } from '../api';
import './Dashboard.css';

const BG = {
  india: 'rgba(0, 0, 0, 0.14)',
  world: 'rgba(2, 151, 159, 0.14)',
  teal: 'rgba(17, 96, 157, 0.14)',
  tealFade: 'linear-gradient(180deg, rgba(17, 96, 157, 0.14) 0%, rgba(12, 12, 13, 0.14) 100%)',
};

const COLORS = {
  tradeBalance: '#22D700',
  gstBalance: '#F4E15C',
  inflation: '#0FCBFF',
  debt: '#0FCBFF',
};

type ChartDatum = Record<string, string | number | undefined>;

interface DashboardProps {
  data: DashboardData;
  onRefresh?: () => void;
  onSignOut?: () => void;
}

const formatPercent = (value: number | null | undefined) =>
  value == null ? '—' : `${toFixed(value, 2)}%`;

const formatLakhCrore = (value: number | null | undefined) =>
  value == null ? '—' : `₹${toFixed(value, 2)} L Cr`;

const formatUsdBillion = (value: number | null | undefined) =>
  value == null ? '—' : `$${toFixed(value, 1)} B`;

const formatDelta = (value: number | null | undefined, suffix = 'pp') =>
  value == null ? undefined : `${value >= 0 ? '+' : ''}${toFixed(value, 2)}${suffix}`;

const valueDomain = (values: Array<number | undefined>, fallback: [number, number]): [number, number] => {
  const present = values.filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!present.length) return fallback;
  const minimum = Math.min(...present);
  const maximum = Math.max(...present);
  if (minimum === maximum) {
    const padding = Math.max(Math.abs(minimum) * 0.15, 1);
    return [minimum - padding, maximum + padding];
  }
  const padding = (maximum - minimum) * 0.15;
  return [Math.min(0, minimum - padding), maximum + padding];
};

// For a line series plotted on its own secondary axis (different unit than
// the bars it shares a chart with): pad its domain with generous headroom
// above the data so the line's dots — and their value-pill labels — stay
// clear of the band near the top of the chart where bar value labels sit,
// instead of colliding with them.
const overlayLineDomain = (values: Array<number | undefined>, fallback: [number, number]): [number, number] => {
  const present = values.filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!present.length) return fallback;
  const minimum = Math.min(...present);
  const maximum = Math.max(...present);
  const range = maximum - minimum || Math.max(Math.abs(maximum), 1);
  return [minimum - range * 0.2, maximum + range * 1.5];
};

const mergeHistory = (series: Record<string, Point[]>) => {
  const records = new Map<string, ChartDatum>();
  for (const [key, points] of Object.entries(series)) {
    for (const point of points) {
      const record = records.get(point.observation_date) ?? {
        period: point.period_label,
        observationDate: point.observation_date,
      };
      record[key] = point.value;
      records.set(point.observation_date, record);
    }
  }
  return [...records.values()].sort((left, right) =>
    String(left.observationDate).localeCompare(String(right.observationDate)),
  );
};

const monthlyAverage = (points: Point[]) => {
  if (!points.length) return null;
  return points.reduce((sum, point) => sum + point.value, 0) / points.length;
};

const gstChartData = (points: Point[]): ChartDatum[] => points.map((point, index) => {
  const previous = points[index - 1]?.value;
  return {
    period: point.period_label,
    collections: point.value,
    growth: previous && previous !== 0 ? ((point.value - previous) / previous) * 100 : undefined,
  };
});

// The Figma reference has five compact x-axis slots. The live GST feed is
// monthly (rather than its mock-up's annual data), so preserve real periods
// while giving each tick the same visual density: “Sep ’26”, not “Sep 2026”.
const compactMonthTick = (value: string | number) => {
  const match = String(value).match(/^([A-Za-z]{3})\s+(\d{4})$/);
  return match ? `${match[1]} ’${match[2].slice(-2)}` : String(value);
};

const ChartEmpty = ({ message }: { message?: string | null }) => (
  <div className="chart-empty" role="status">
    {message ?? 'No validated data is available for this chart.'}
  </div>
);

const sourceProps = (indicator: Indicator | undefined) => {
  const freshnessStatus = indicator?.freshness_status ?? 'unavailable';
  const isUnavailable = freshnessStatus === 'unavailable' || freshnessStatus === 'missing';
  return {
    source: indicator?.source,
    asOfDate: indicator?.as_of_date,
    freshnessStatus,
    // Only fall back to this text when there genuinely is no observation —
    // fresh/stale indicators already carry their own message (or none needed).
    message: indicator?.message ?? (isUnavailable ? 'No validated observation is available from this source yet.' : undefined),
  };
};

export const Dashboard: React.FC<DashboardProps> = ({ data, onRefresh, onSignOut }) => {
  const getIndicator = (id: string) => data.indicators.find((indicator) => indicator.indicator.id === id);

  const gdpIndia = getIndicator('gdp_growth_india');
  const gdpWorld = getIndicator('gdp_growth_world');
  const debt = getIndicator('debt_to_gdp_india');
  const debtUs = getIndicator('debt_to_gdp_us');
  const imports = getIndicator('imports_india');
  const exports = getIndicator('exports_india');
  const tradeBalance = getIndicator('trade_balance_india');
  const gst = getIndicator('gst_collection_india');
  const inflation = getIndicator('inflation_india');
  const governmentExpenditure = getIndicator('government_expenditure_india');
  const capitalExpenditure = getIndicator('government_capital_expenditure_india');

  const gdpData = mergeHistory({ india: gdpIndia?.history ?? [], world: gdpWorld?.history ?? [] });
  const debtData = (debt?.history ?? []).map((point) => ({ period: point.period_label, value: point.value }));
  const tradeData = mergeHistory({
    imports: imports?.history ?? [],
    exports: exports?.history ?? [],
    tradeBalance: tradeBalance?.history ?? [],
  });
  // The design allocates five evenly spaced categories. Show the newest five
  // official releases rather than cramming all retained monthly observations
  // into the same fixed-width chart.
  const gstData = gstChartData(gst?.history ?? []).slice(-5);
  const inflationData = (inflation?.history ?? []).map((point) => ({ period: point.period_label, value: point.value }));
  const expenditureData = mergeHistory({
    total: governmentExpenditure?.history ?? [],
    capital: capitalExpenditure?.history ?? [],
  }).map((point): ChartDatum => {
    const total = typeof point.total === 'number' ? point.total : 0;
    const capital = typeof point.capital === 'number' ? point.capital : 0;
    return {
      ...point,
      revenue: Math.max(total - capital, 0),
      capital,
    };
  });

  const A = {
    india: '/figma-assets/india.png',
    world: '/figma-assets/world.png',
    trade: '/figma-assets/trade.png',
    gst: '/figma-assets/gst.png',
    gstAvg: '/figma-assets/gst-avg.png',
    inflation: '/figma-assets/inflation.png',
    rbi: '/figma-assets/rbi.png',
    govt: '/figma-assets/expenditure.png',
    us: '/figma-assets/us.png',
  };

  return (
    <div className="dashboard-shell">
      <TitleBar onRefresh={onRefresh} onSignOut={onSignOut} />
      <TickerBar items={data.ticker} />

      <main className="dashboard-grid" aria-label="Economic indicators dashboard">

        {/* ── 1. GDP Growth ─────────────────────────────────────────────── */}
        <IndicatorCard title="GDP Growth - India vs World" subtitle="(YOY%)" subtitleColor="cyan" animationDelay={0} ariaLabel="GDP Growth - India vs World" {...sourceProps(gdpIndia)}>
          <div className="kpi-row">
            <KPISubCard
              label={gdpIndia?.period_label ? `India (${gdpIndia.period_label})` : 'India'}
              value={formatPercent(gdpIndia?.value)}
              delta={formatDelta(gdpIndia?.change)}
              deltaPositive={(gdpIndia?.change ?? 0) >= 0}
              cardBg={BG.india}
              flagMode
              imageSrc={A.india}
            />
            <KPISubCard
              label={gdpWorld?.period_label ? `World (${gdpWorld.period_label})` : 'World'}
              value={formatPercent(gdpWorld?.value)}
              delta={formatDelta(gdpWorld?.change)}
              deltaPositive={(gdpWorld?.change ?? 0) >= 0}
              cardBg={BG.world}
              flagMode
              imageSrc={A.world}
            />
          </div>
          <ChartLegend items={[{ label: 'India', type: 'bar-blue' }, { label: 'World', type: 'bar-amber' }]} />
          {gdpData.length
            ? <GroupedBarChart data={gdpData} xKey="period" seriesA={{ key: 'india', label: 'India', gradient: 'blue' }} seriesB={{ key: 'world', label: 'World', gradient: 'amber' }} yDomain={valueDomain(gdpData.flatMap((p) => [p.india as number | undefined, p.world as number | undefined]), [0, 10])} ariaLabel="Grouped bar chart showing GDP growth for India and the world" />
            : <ChartEmpty message={gdpIndia?.message ?? gdpWorld?.message} />}
        </IndicatorCard>

        {/* ── 2. Debt to GDP ────────────────────────────────────────────── */}
        <IndicatorCard title="Debt to GDP Ratio" subtitle="(IND)" subtitleColor="cyan" animationDelay={60} ariaLabel="Debt to GDP Ratio" {...sourceProps(debt)}>
          <div className="kpi-row">
            <KPISubCard
              label={debt?.period_label ? `India (${debt.period_label})` : 'India (FY25)'}
              value={formatPercent(debt?.value)}
              delta={formatDelta(debt?.change)}
              deltaPositive={(debt?.change ?? 0) >= 0}
              cardBg={BG.teal}
              flagMode
              imageSrc={A.india}
            />
            <KPISubCard
              label={debtUs?.period_label ? `US (${debtUs.period_label})` : 'US'}
              value={formatPercent(debtUs?.value)}
              delta={formatDelta(debtUs?.change)}
              deltaPositive={(debtUs?.change ?? 0) >= 0}
              cardBg={BG.teal}
              flagMode
              imageSrc={A.us}
            />
          </div>
          {debtData.length
            ? <AreaLineChart data={debtData} xKey="period" dataKey="value" lineColor={COLORS.debt} yDomain={valueDomain(debtData.map((p) => p.value), [0, 100])} yTickFormatter={(v) => `${Math.round(v)}%`} ariaLabel="Area chart showing India debt to GDP ratio" />
            : <ChartEmpty message={debt?.message} />}
        </IndicatorCard>

        {/* ── 3. Imports, Exports & Trade Balance ───────────────────────── */}
        <IndicatorCard title="Imports, Exports & Trade Balance" animationDelay={120} ariaLabel="Imports, exports and trade balance" {...sourceProps(tradeBalance)}>
          <div className="kpi-row">
            <KPISubCard
              label="Exports"
              value={formatUsdBillion(exports?.value)}
              delta={formatDelta(exports?.change, ' B')}
              deltaPositive={(exports?.change ?? 0) >= 0}
              cardBg={BG.teal}
              imageSrc={A.trade}
              imageObjectPosition="0% 50%"
            />
            <KPISubCard
              label="Imports"
              value={formatUsdBillion(imports?.value)}
              delta={formatDelta(imports?.change, ' B')}
              deltaPositive={(imports?.change ?? 0) >= 0}
              cardBg={BG.tealFade}
              imageSrc={A.trade}
              imageObjectPosition="100% 50%"
            />
          </div>
          <ChartLegend items={[{ label: 'Imports', type: 'bar-blue' }, { label: 'Exports', type: 'bar-amber' }, { label: 'Trade Balance', type: 'line-green' }]} />
          {tradeData.length
            ? <MixedBarLineChart data={tradeData} xKey="period" barSeriesA={{ key: 'imports', label: 'Imports' }} barSeriesB={{ key: 'exports', label: 'Exports' }} lineKey="tradeBalance" lineLabel="Trade Balance" lineColor={COLORS.tradeBalance} yDomain={valueDomain(tradeData.flatMap((p) => [p.imports as number | undefined, p.exports as number | undefined, p.tradeBalance as number | undefined]), [0, 10])} yTickFormatter={(v) => `$${toFixed(v, 0)}B`} ariaLabel="Mixed chart showing India imports, exports and trade balance" />
            : <ChartEmpty message={tradeBalance?.message} />}
        </IndicatorCard>

        {/* ── 4. GST Tax Collection ─────────────────────────────────────── */}
        <IndicatorCard title="GST Tax Collection" subtitle="(YOY%)" subtitleColor="amber" animationDelay={180} ariaLabel="GST Tax Collection" {...sourceProps(gst)}>
          <div className="kpi-row">
            <KPISubCard
              label="GST Collections"
              value={formatLakhCrore(gst?.value)}
              delta={formatDelta(gst?.change, ' L Cr')}
              deltaPositive={(gst?.change ?? 0) >= 0}
              cardBg={BG.tealFade}
              imageSrc={A.gst}
            />
            <KPISubCard
              label="Monthly Average"
              value={formatLakhCrore(monthlyAverage(gst?.history ?? []))}
              cardBg={BG.teal}
              imageSrc={A.gstAvg}
            />
          </div>
          <ChartLegend items={[{ label: 'GST Collections', type: 'bar-blue' }, { label: 'Month-on-month growth', type: 'line-yellow' }]} />
          {gstData.length
            ? <MixedBarLineChart
                data={gstData}
                xKey="period"
                barSeriesA={{ key: 'collections', label: 'GST Collections' }}
                lineKey="growth"
                lineLabel="Month-on-month growth"
                lineColor={COLORS.gstBalance}
                yDomain={valueDomain(gstData.map((p) => p.collections as number | undefined), [0, 10])}
                lineYDomain={overlayLineDomain(gstData.map((p) => p.growth as number | undefined), [-10, 10])}
                yTickFormatter={(v) => `₹${toFixed(v, 1)}`}
                xTickFormatter={compactMonthTick}
                ariaLabel="Combined chart showing monthly GST collections and month-on-month growth"
              />
            : <ChartEmpty message={gst?.message} />}
        </IndicatorCard>

        {/* ── 5. Inflation ──────────────────────────────────────────────── */}
        <IndicatorCard title="Inflation" subtitle="(IND)" subtitleColor="cyan" animationDelay={240} ariaLabel="Inflation India" {...sourceProps(inflation)}>
          <div className="kpi-row">
            <KPISubCard
              label="Inflation Rate"
              value={formatPercent(inflation?.value)}
              delta={formatDelta(inflation?.change)}
              deltaPositive={(inflation?.change ?? 0) >= 0}
              cardBg={BG.teal}
              imageSrc={A.inflation}
            />
            <KPISubCard
              label="RBI Target"
              value={formatPercent(inflation?.comparison_value)}
              cardBg={BG.teal}
              imageSrc={A.rbi}
              imageObjectPosition="100% 50%"
            />
          </div>
          {inflationData.length
            ? <AreaLineChart data={inflationData} xKey="period" dataKey="value" lineColor={COLORS.inflation} yDomain={valueDomain(inflationData.map((p) => p.value), [0, 10])} yTickFormatter={(v) => `${Math.round(v)}%`} ariaLabel="Area chart showing India inflation" />
            : <ChartEmpty message={inflation?.message} />}
        </IndicatorCard>

        {/* ── 6. Government Expenditure ─────────────────────────────────── */}
        <IndicatorCard title="Government Expenditure" animationDelay={300} ariaLabel="Government expenditure" {...sourceProps(governmentExpenditure)}>
          <div className="kpi-row">
            <KPISubCard
              label="Total Expenditure"
              value={formatLakhCrore(governmentExpenditure?.value)}
              delta={formatDelta(governmentExpenditure?.change, ' L Cr')}
              deltaPositive={(governmentExpenditure?.change ?? 0) >= 0}
              cardBg={BG.teal}
              imageSrc={A.govt}
              imageObjectPosition="0% 50%"
            />
            <KPISubCard
              label="Capital Expenditure"
              value={formatLakhCrore(capitalExpenditure?.value)}
              delta={formatDelta(capitalExpenditure?.change, ' L Cr')}
              deltaPositive={(capitalExpenditure?.change ?? 0) >= 0}
              cardBg={BG.teal}
              imageSrc={A.govt}
              imageObjectPosition="100% 50%"
            />
          </div>
          <ChartLegend items={[{ label: 'Revenue Expenditure', type: 'bar-blue' }, { label: 'Capital Expenditure', type: 'bar-amber' }]} />
          {expenditureData.length
            ? <GroupedBarChart data={expenditureData} xKey="period" stacked seriesA={{ key: 'revenue', label: 'Revenue Expenditure', gradient: 'blue-indigo' }} seriesB={{ key: 'capital', label: 'Capital Expenditure', gradient: 'amber' }} yDomain={valueDomain(expenditureData.flatMap((p) => [p.total as number | undefined, p.capital as number | undefined]), [0, 50])} yTickFormatter={(v) => `₹${toFixed(v, 0)}L`} valueFormatter={(v) => toFixed(v, 1)} ariaLabel="Stacked bar chart showing revenue and capital government expenditure" />
            : <ChartEmpty message={governmentExpenditure?.message ?? capitalExpenditure?.message} />}
        </IndicatorCard>
      </main>
    </div>
  );
};
