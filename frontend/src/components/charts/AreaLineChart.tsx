import React, { memo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { toFixed, toPct } from '../../utils/format';
import { PlotBorder } from './PlotBorder';
import './Charts.css';

interface DataPoint {
  [key: string]: string | number;
}
type TooltipEntry = { name: string; color?: string; value?: string | number | [number, number] };
type TooltipProps = { active?: boolean; payload?: TooltipEntry[]; label?: string };
// In Recharts Area, the dot's 'value' prop is [baseValue, actualValue]
type DotProps = { cx?: number; cy?: number; value?: string | number | [number, number] };

interface AreaLineChartProps {
  data: DataPoint[];
  xKey: string;
  dataKey: string;
  lineColor?: string;
  yDomain?: [number, number];
  yTicks?: number[];
  yTickFormatter?: (v: number) => string;
  ariaLabel?: string;
}

// Custom Y-Axis tick that directly renders the raw tick value
type AxisTickProps = {
  x?: number | string;
  y?: number | string;
  payload?: { value: number };
  formatter: (v: number) => string;
  [key: string]: unknown;
};
const AxisTick = ({ x = 0, y = 0, payload, formatter }: AxisTickProps) => (
  <text
    x={x}
    y={y}
    dy={4}
    textAnchor="end"
    fill="#CCCCCC"
    fontSize={16}
    fontWeight={600}
    fontFamily="'Segoe UI', Inter, sans-serif"
  >
    {payload ? formatter(payload.value) : ''}
  </text>
);

const CustomTooltip = ({ active, payload, label }: TooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip__label">{label}</span>
      {payload.map((entry) => {
        // Area charts pass value as [baseValue, actualValue]
        const raw = Array.isArray(entry.value) ? entry.value[1] : entry.value;
        const display = typeof raw === 'number' ? toFixed(raw, 2) : raw;
        return (
          <div key={entry.name} className="chart-tooltip__row">
            <span className="chart-tooltip__swatch" style={{ background: entry.color }} />
            <span><strong>{display}</strong></span>
          </div>
        );
      })}
    </div>
  );
};

// Figma: callout pill dot on each data point
// Figma: circle cx/cy r=5, fill white; rect pill above with value
const CalloutDot = ({ cx, cy, value, lineColor }: DotProps & { lineColor: string }) => {
  if (!cx || !cy) return null;
  // Recharts Area passes value as [baseValue, actualValue] – extract actual
  const rawVal = Array.isArray(value) ? value[1] : value;
  const numVal = typeof rawVal === 'number' ? rawVal : Number(rawVal);
  const label = !isNaN(numVal) ? toPct(numVal, 1) : String(rawVal ?? '');
  const pillW = label.length * 7 + 8;
  return (
    <g>
      {/* Figma: Ellipse dot – circle r=5, #22D700 / lineColor */}
      <circle cx={cx} cy={cy} r={5} fill={lineColor} />
      {/* Figma: pill callout – black semi-transparent bg, rounded, value text */}
      <rect
        x={cx - pillW / 2}
        y={cy - 26}
        width={pillW}
        height={18}
        rx={9}
        fill="rgba(0,0,0,0.55)"
      />
      <text
        x={cx}
        y={cy - 13}
        textAnchor="middle"
        fill="#CCCCCC"
        fontSize={11}
        fontWeight={600}
        fontFamily="'Segoe UI', Inter, sans-serif"
      >
        {label}
      </text>
    </g>
  );
};

export const AreaLineChart: React.FC<AreaLineChartProps> = memo(({
  data, xKey, dataKey,
  lineColor = '#0FCBFF',
  yDomain = [0, 10],
  yTicks,
  yTickFormatter,
  ariaLabel,
}) => {
  const yFmt = yTickFormatter ?? ((v: number) => `${Math.round(v)}%`);
  const gradId = `area-grad-${dataKey}`;

  return (
    <div className="chart-wrapper" role="img" aria-label={ariaLabel ?? 'Area chart'}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 28, right: 10, left: 0, bottom: 0 }}
        >
          <defs>
            {/* Figma: gradient fill under line – lineColor → transparent */}
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.35} />
              <stop offset="70%" stopColor={lineColor} stopOpacity={0.08} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          {/* Figma: horizontal dashed gridlines – #5B5B5B */}
          <CartesianGrid
            vertical={false}
            stroke="#5B5B5B"
            strokeOpacity={0.6}
          />
          {/* Figma: X axis – #cccccc, Segoe UI Semibold 16px */}
          <XAxis
            dataKey={xKey}
            tick={{ fill: '#CCCCCC', fontSize: 16, fontWeight: 600, fontFamily: "'Segoe UI', Inter, sans-serif" }}
            axisLine={false}
            tickLine={false}
          />
          {/* Figma: Y axis – #cccccc, Segoe UI Semibold 16–19px */}
          <YAxis
            domain={yDomain}
            ticks={yTicks}
            tick={(props) => <AxisTick {...props} formatter={yFmt} />}
            axisLine={false}
            tickLine={false}
            width={54}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1 }} />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={lineColor}
            strokeWidth={3}
            fill={`url(#${gradId})`}
            dot={(dotProps: DotProps) => (
              <CalloutDot
                {...dotProps}
                lineColor={lineColor}
              />
            )}
            activeDot={{ r: 7, fill: '#fff', stroke: lineColor, strokeWidth: 2 }}
            isAnimationActive={true}
            animationDuration={900}
            animationEasing="ease-in-out"
          />
          <PlotBorder />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
});

AreaLineChart.displayName = 'AreaLineChart';
