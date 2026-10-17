import { usePlotArea } from 'recharts';

/**
 * Figma: the chart plot area has a thin light-gray border with sharp top
 * corners and rounded bottom corners — square where it meets the Y-axis
 * labels and X-axis labels (which sit outside the border), rounded at the
 * bottom. Drawn from the exact plot-area bounds so axis labels are excluded.
 */
export const PlotBorder = ({ radius = 10 }: { radius?: number }) => {
  const area = usePlotArea();
  if (!area) return null;
  const { x, y, width, height } = area;
  const r = Math.min(radius, width / 2, height / 2);
  const d = [
    `M ${x},${y}`,
    `L ${x + width},${y}`,
    `L ${x + width},${y + height - r}`,
    `A ${r},${r} 0 0 1 ${x + width - r},${y + height}`,
    `L ${x + r},${y + height}`,
    `A ${r},${r} 0 0 1 ${x},${y + height - r}`,
    'Z',
  ].join(' ');
  return (
    <path
      d={d}
      fill="none"
      stroke="rgba(255, 255, 255, 0.45)"
      strokeWidth={1}
    />
  );
};
