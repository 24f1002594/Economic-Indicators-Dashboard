import React from 'react';
import './ChartLegend.css';

export type LegendItemType = 'bar-blue' | 'bar-amber' | 'line-green' | 'line-yellow' | 'line-cyan' | 'area-cyan';

export interface LegendItem {
  label: string;
  type: LegendItemType;
}

interface ChartLegendProps {
  items: LegendItem[];
}

/**
 * Figma exact legend swatch styles:
 * – India (bar-blue):   linear-gradient(↑, #18647C → #107494)
 * – World (bar-amber):  linear-gradient(↓, #FFA73F → #996426)
 * – Trade Balance line: #22D700 green with circle dot
 * – GST line:           #F4E15C yellow with circle dot
 * Width/height: 16×16px, border-radius 3px for bars
 */
const SWATCH_MAP: Record<LegendItemType, { background: string; isLine: boolean }> = {
  'bar-blue':   {
    background: 'linear-gradient(180deg, #107494 0%, #18647C 100%)',
    isLine: false,
  },
  'bar-amber':  {
    background: 'linear-gradient(180deg, #FFA73F 0%, #996426 100%)',
    isLine: false,
  },
  'line-green': { background: '#22D700',  isLine: true },
  'line-yellow':{ background: '#F4E15C',  isLine: true },
  'line-cyan':  { background: '#0FCBFF',  isLine: true },
  'area-cyan':  { background: '#0FCBFF',  isLine: true },
};

export const ChartLegend: React.FC<ChartLegendProps> = ({ items }) => {
  return (
    <div className="chart-legend" aria-hidden="true">
      {items.map((item) => {
        const swatch = SWATCH_MAP[item.type];
        return (
          <span key={item.label} className="chart-legend__item">
            {swatch.isLine ? (
              /* Figma: line indicator – Vector 1632 style: 22px line with centre dot */
              <span
                className="chart-legend__indicator chart-legend__indicator--line"
                style={{ background: swatch.background }}
              />
            ) : (
              /* Figma: 16×16px rect, border-radius 3px, exact gradient */
              <span
                className="chart-legend__indicator chart-legend__indicator--bar"
                style={{ background: swatch.background }}
              />
            )}
            <span className="chart-legend__label">{item.label}</span>
          </span>
        );
      })}
    </div>
  );
};
