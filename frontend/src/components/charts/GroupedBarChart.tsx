import React, { memo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
} from 'recharts';
import { toFixed, toPct } from '../../utils/format';
import { PlotBorder } from './PlotBorder';
import './Charts.css';

type ChartDatum = Record<string, string | number | undefined>;
type TooltipEntry = { name: string; color?: string; value?: string | number };
type TooltipProps = { active?: boolean; payload?: TooltipEntry[]; label?: string };
type BarShapeProps = { x?: number; y?: number; width?: number; height?: number; fill?: string };
type ValueLabelProps = {
  x?: string | number;
  y?: string | number;
  width?: string | number;
  height?: string | number;
  value?: unknown;
};

// ── Shared tooltip ──────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: TooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip__label">{label}</span>
      {payload.map((entry) => (
        <div key={entry.name} className="chart-tooltip__row">
          <span className="chart-tooltip__swatch" style={{ background: entry.color }} />
          <span>{entry.name}: <strong>{typeof entry.value === 'number' ? toFixed(entry.value, 1) : entry.value}</strong></span>
        </div>
      ))}
    </div>
  );
};

// ── Custom bar shape with rounded top ───────────────────────────────────────
const RoundedBar = ({ x = 0, y = 0, width = 0, height = 0, fill = 'none' }: BarShapeProps) => {
  if (height <= 0) return null;
  const r = Math.min(4, width / 2);
  return (
    <path
      d={`M${x},${y + height} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + width - r},${y} Q${x + width},${y} ${x + width},${y + r} L${x + width},${y + height} Z`}
      fill={fill}
    />
  );
};

// ── Value label above bar – Figma: #cccccc, SegoeUi-Semibold ──────────────
const ValueLabel = ({
  x = 0, y = 0, width = 0, value, formatter,
}: ValueLabelProps & { formatter: (v: number) => string }) => {
  const numX = Number(x);
  const numY = Number(y);
  const numWidth = Number(width);
  if (value == null) return null;
  if (numWidth < 9) return null;
  const numVal = typeof value === 'number' ? value : Number(value);
  if (isNaN(numVal)) return null;
  return (
    <text
      x={numX + numWidth / 2}
      y={numY - 4}
      textAnchor="middle"
      fill="#CCCCCC"
      fontSize={numWidth < 20 ? 9 : 11}
      fontWeight={600}
      fontFamily="'Segoe UI', Inter, sans-serif"
    >
      {formatter(numVal)}
    </text>
  );
};

const InnerLabel = ({
  x = 0, y = 0, width = 0, height = 0, value, formatter,
}: ValueLabelProps & { formatter: (v: number) => string }) => {
  const numX = Number(x);
  const numY = Number(y);
  const numWidth = Number(width);
  const numHeight = Number(height);
  if (value == null || numHeight < 18 || numWidth < 16) return null;
  const numVal = typeof value === 'number' ? value : Number(value);
  if (isNaN(numVal)) return null;
  return (
    <text
      x={numX + numWidth / 2}
      y={numY + numHeight / 2 + 4}
      textAnchor="middle"
      fill="#FFFFFF"
      fontSize={11}
      fontWeight={600}
      fontFamily="'Segoe UI', Inter, sans-serif"
    >
      {formatter(numVal)}
    </text>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// GroupedBarChart  (GDP Growth, Govt Expenditure)
// ────────────────────────────────────────────────────────────────────────────
interface GroupedBarChartProps {
  data: ChartDatum[];
  xKey: string;
  seriesA: { key: string; label: string; gradient: 'blue' | 'amber' | 'blue-indigo' };
  seriesB?: { key: string; label: string; gradient: 'blue' | 'amber' | 'blue-indigo' };
  yDomain?: [number, number];
  yTickFormatter?: (v: number) => string;
  valueFormatter?: (v: number) => string;
  stacked?: boolean;
  ariaLabel?: string;
}

export const GroupedBarChart: React.FC<GroupedBarChartProps> = memo(({
  data, xKey, seriesA, seriesB, yDomain = [0, 10], yTickFormatter, valueFormatter, stacked = false, ariaLabel,
}) => {
  const yFmt = yTickFormatter ?? ((v: number) => `${Math.round(v)}%`);
  const labelFmt = valueFormatter ?? ((v: number) => toPct(v, 1));

  return (
    <div className="chart-wrapper" role="img" aria-label={ariaLabel ?? 'Bar chart'}>
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          {/*
            Figma India bars (blue):
            linear-gradient(1deg, #061E44 0%, #0FB8E6 100%) – near-vertical, bottom to top
          */}
          <linearGradient id="grad-blue" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#061E44" />
            <stop offset="100%" stopColor="#0FB8E6" />
          </linearGradient>
          {/*
            Figma World bars (amber):
            linear-gradient(180deg, #FFB012 0%, #844B08 100%) – top to bottom
          */}
          <linearGradient id="grad-amber" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFB012" />
            <stop offset="100%" stopColor="#844B08" />
          </linearGradient>
          {/*
            Figma Revenue Expenditure (blue-indigo):
            linear-gradient(1deg, #0FB8E6 0%, #0046B7 100%)
          */}
          <linearGradient id="grad-blue-indigo" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#0FB8E6" />
            <stop offset="100%" stopColor="#0046B7" />
          </linearGradient>
        </defs>
      </svg>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 24, right: 8, left: 0, bottom: 0 }}
          barCategoryGap="30%"
          barGap={3}
        >
          {/* Figma: horizontal dashed gridlines – #5B5B5B */}
          <CartesianGrid
            vertical={false}
            stroke="#5B5B5B"
            strokeOpacity={0.6}
            strokeDasharray=""
          />
          {/* Figma: X axis – #cccccc, Segoe UI Semibold 16px */}
          <XAxis
            dataKey={xKey}
            tick={{ fill: '#CCCCCC', fontSize: 16, fontWeight: 600, fontFamily: "'Segoe UI', Inter, sans-serif" }}
            axisLine={false}
            tickLine={false}
          />
          {/* Figma: Y axis – #cccccc, Segoe UI Semibold 16px */}
          <YAxis
            domain={yDomain}
            tickFormatter={yFmt}
            tick={{ fill: '#CCCCCC', fontSize: 16, fontWeight: 600, fontFamily: "'Segoe UI', Inter, sans-serif" }}
            axisLine={false}
            tickLine={false}
            width={58}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <PlotBorder />
          <Bar
            dataKey={seriesA.key}
            name={seriesA.label}
            stackId={stacked ? 'stack' : undefined}
            shape={stacked ? undefined : <RoundedBar fill={`url(#grad-${seriesA.gradient})`} />}
            fill={`url(#grad-${seriesA.gradient})`}
            isAnimationActive={true}
            animationDuration={600}
            animationEasing="ease-out"
          >
            <LabelList dataKey={seriesA.key} content={stacked
              ? (props) => <InnerLabel {...props} formatter={labelFmt} />
              : (props) => <ValueLabel {...props} formatter={labelFmt} />}
            />
          </Bar>
          {seriesB && (
            <Bar
              dataKey={seriesB.key}
              name={seriesB.label}
              stackId={stacked ? 'stack' : undefined}
              shape={<RoundedBar fill={`url(#grad-${seriesB.gradient})`} />}
              fill={`url(#grad-${seriesB.gradient})`}
              isAnimationActive={true}
              animationDuration={600}
              animationEasing="ease-out"
              animationBegin={100}
            >
              <LabelList dataKey={seriesB.key} content={stacked
                ? (props) => <InnerLabel {...props} formatter={labelFmt} />
                : (props) => <ValueLabel {...props} formatter={labelFmt} />}
              />
              {stacked && (
                <LabelList
                  dataKey="total"
                  content={(props) => <ValueLabel {...props} formatter={labelFmt} />}
                />
              )}
            </Bar>
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

GroupedBarChart.displayName = 'GroupedBarChart';
