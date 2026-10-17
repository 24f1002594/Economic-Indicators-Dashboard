import React, { memo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
} from 'recharts';
import { toFixed } from '../../utils/format';
import { PlotBorder } from './PlotBorder';
import './Charts.css';

type ChartDatum = Record<string, string | number | undefined>;
type TooltipEntry = { name: string; color?: string; stroke?: string; value?: string | number };
type TooltipProps = { active?: boolean; payload?: TooltipEntry[]; label?: string };
type BarShapeProps = { x?: number; y?: number; width?: number; height?: number; fill?: string };
type DotProps = { cx?: number; cy?: number; value?: string | number; color?: string };
type ValueLabelProps = { x?: number; y?: number; width?: number; value?: string | number };

interface MixedBarLineChartProps {
  data: ChartDatum[];
  xKey: string;
  barSeriesA?: { key: string; label: string };
  barSeriesB?: { key: string; label: string };
  lineKey: string;
  lineLabel: string;
  lineColor?: string;
  yDomain?: [number, number];
  yTickFormatter?: (v: number) => string;
  xTickFormatter?: (v: string | number) => string;
  /**
   * When the line series is a different unit than the bars (e.g. a growth
   * percentage next to a currency value), pass its own domain here so it
   * gets a second, independent (hidden) axis instead of being squashed
   * onto the bars' scale — which would blow out the shared Y range.
   */
  lineYDomain?: [number, number];
  ariaLabel?: string;
}

const CustomTooltip = ({ active, payload, label }: TooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip__label">{label}</span>
      {payload.map((entry) => (
        <div key={entry.name} className="chart-tooltip__row">
          <span className="chart-tooltip__swatch" style={{ background: entry.color ?? entry.stroke }} />
          <span>{entry.name}: <strong>{typeof entry.value === 'number' ? toFixed(entry.value, 2) : entry.value}</strong></span>
        </div>
      ))}
    </div>
  );
};

// Rounded bar shape – Figma: border-radius 4px
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

// Figma: value labels above bars – "6.3" in rounded pill, Segoe UI 15px #CCCCCC
const ValueLabel = ({ x = 0, y = 0, width = 0, value }: ValueLabelProps) => {
  if (value == null) return null;
  if (width < 9) return null;
  const numVal = typeof value === 'number' ? value : Number(value);
  const label = !isNaN(numVal) ? toFixed(numVal, 1) : String(value);
  const pillW = 34;
  return (
    <g>
      <rect
        x={x + width / 2 - pillW / 2}
        y={y - 22}
        width={pillW}
        height={18}
        rx={9}
        fill="rgba(0,0,0,0.45)"
      />
      <text
        x={x + width / 2}
        y={y - 9}
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

// Figma: line dots – Ellipse 3357/3358/3359/3360/3361/3362 – r=5 filled circle
const LineDot = ({ cx, cy, value, color }: DotProps) => {
  if (!cx || !cy) return null;
  const numVal = typeof value === 'number' ? value : Number(value);
  const label = !isNaN(numVal) ? toFixed(numVal, 1) : String(value ?? '');
  const pillW = label.length * 7 + 8;
  return (
    <g>
      <circle cx={cx} cy={cy} r={5} fill={color ?? '#22D700'} />
      {/* Figma: value pill sits below the dot, not above */}
      <rect
        x={cx - pillW / 2}
        y={cy + 8}
        width={pillW}
        height={18}
        rx={9}
        fill="rgba(0,0,0,0.55)"
      />
      <text
        x={cx}
        y={cy + 21}
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

export const MixedBarLineChart: React.FC<MixedBarLineChartProps> = memo(({
  data, xKey,
  barSeriesA, barSeriesB,
  lineKey, lineLabel,
  lineColor = '#22D700',
  yDomain = [0, 10],
  yTickFormatter,
  xTickFormatter,
  lineYDomain,
  ariaLabel,
}) => {
  const yFmt = yTickFormatter ?? ((v: number) => `${Math.round(v)}%`);

  return (
    <div className="chart-wrapper" role="img" aria-label={ariaLabel ?? 'Mixed bar and line chart'}>
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          {/* Figma Imports (blue): linear-gradient(1deg, #061E44 0%, #0FB8E6 100%) */}
          <linearGradient id="mc-grad-blue" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#061E44" />
            <stop offset="100%" stopColor="#0FB8E6" />
          </linearGradient>
          {/* Figma Exports (amber): linear-gradient(180deg, #FFB012 0%, #844B08 100%) */}
          <linearGradient id="mc-grad-amber" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FFB012" />
            <stop offset="100%" stopColor="#844B08" />
          </linearGradient>
          {/* Figma Revenue Expenditure blue-indigo */}
          <linearGradient id="mc-grad-blue-indigo" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#0FB8E6" />
            <stop offset="100%" stopColor="#0046B7" />
          </linearGradient>
        </defs>
      </svg>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 28, right: 10, left: 0, bottom: 0 }}
          barCategoryGap="30%"
          barGap={3}
        >
          {/* Figma: horizontal gridlines – #5B5B5B solid */}
          <CartesianGrid
            vertical={false}
            stroke="#5B5B5B"
            strokeOpacity={0.6}
          />
          {/* Figma: X axis – #cccccc, Segoe UI Semibold 16px */}
          <XAxis
            dataKey={xKey}
            tickFormatter={xTickFormatter}
            tick={{ fill: '#CCCCCC', fontSize: 16, fontWeight: 600, fontFamily: "'Segoe UI', Inter, sans-serif" }}
            axisLine={false}
            tickLine={false}
          />
          {/* Figma: Y axis – #cccccc, Segoe UI Semibold 16px */}
          <YAxis
            yAxisId="left"
            domain={yDomain}
            tickFormatter={yFmt}
            tick={{ fill: '#CCCCCC', fontSize: 16, fontWeight: 600, fontFamily: "'Segoe UI', Inter, sans-serif" }}
            axisLine={false}
            tickLine={false}
            width={58}
          />
          {lineYDomain && (
            <YAxis yAxisId="right" orientation="right" domain={lineYDomain} hide />
          )}
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <PlotBorder />
          {barSeriesA && (
            <Bar
              yAxisId="left"
              dataKey={barSeriesA.key}
              name={barSeriesA.label}
              shape={<RoundedBar fill="url(#mc-grad-blue)" />}
              fill="url(#mc-grad-blue)"
              isAnimationActive={true}
              animationDuration={600}
              animationEasing="ease-out"
            >
              <LabelList content={<ValueLabel />} />
            </Bar>
          )}
          {barSeriesB && (
            <Bar
              yAxisId="left"
              dataKey={barSeriesB.key}
              name={barSeriesB.label}
              shape={<RoundedBar fill="url(#mc-grad-amber)" />}
              fill="url(#mc-grad-amber)"
              isAnimationActive={true}
              animationDuration={600}
              animationEasing="ease-out"
              animationBegin={80}
            >
              <LabelList content={<ValueLabel />} />
            </Bar>
          )}
          {/* Figma: Trade Balance line – #22D700 green, strokeWidth 2 */}
          <Line
            yAxisId={lineYDomain ? 'right' : 'left'}
            type="monotone"
            dataKey={lineKey}
            name={lineLabel}
            stroke={lineColor}
            strokeWidth={2}
            dot={(dotProps: DotProps) => <LineDot {...dotProps} color={lineColor} />}
            activeDot={{ r: 6, fill: lineColor, stroke: '#fff', strokeWidth: 2 }}
            isAnimationActive={true}
            animationDuration={800}
            animationEasing="ease-in-out"
            animationBegin={400}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
});

MixedBarLineChart.displayName = 'MixedBarLineChart';
