import React from 'react';
import './TickerBar.css';

interface TickerItem {
  symbol: string;
  last_price: number | null;
  change_percent: number | null;
  as_of: string | null;
  freshness_status: 'fresh' | 'stale' | 'unavailable' | 'missing';
  source: { name: string };
}

interface TickerBarProps {
  items: TickerItem[];
}

export const TickerBar: React.FC<TickerBarProps> = ({ items }) => {
  // Triple for seamless marquee loop
  const tape = [...items, ...items, ...items];
  const status = items.length === 0 || items.some((item) => item.freshness_status === 'unavailable' || item.freshness_status === 'missing')
    ? 'unavailable'
    : items.some((item) => item.freshness_status === 'stale')
      ? 'stale'
      : 'fresh';
  const statusLabel = status === 'fresh' ? 'LIVE' : status.toUpperCase();

  return (
    <section className="ticker-bar" aria-label="Live market ticker" aria-live="polite">
      {/* LIVE Badge – exact Figma: 92×29px, #D62D2A bg, 1px #FF0000 border, radius 6.85px */}
      <div className={`ticker-bar__live ticker-bar__live--${status}`} aria-label={`Market ticker ${status}`}>
        <span className="ticker-bar__live-text">{statusLabel}</span>
        {/* Figma: plain live-pulse dot, 14×14px, stroke #FFACAC — not a flag */}
        <span className="ticker-bar__live-flag" aria-hidden="true" />
      </div>

      {/* Accessible, non-redundant summary for screen readers; the scrolling
          tape below is decorative and hidden from assistive tech. */}
      <ul className="sr-only">
        {items.map((item) => {
          const isPositive = (item.change_percent ?? 0) >= 0;
          const changeStr = item.change_percent != null
            ? `${isPositive ? 'up' : 'down'} ${Math.abs(item.change_percent).toFixed(2)}%`
            : 'change unavailable';
          const priceStr = item.last_price != null
            ? item.last_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })
            : 'unavailable';
          return <li key={item.symbol}>{item.symbol}: {priceStr}, {changeStr}</li>;
        })}
      </ul>

      {/* First vertical divider – Figma: Line 6, 38.43px, #415D88 */}
      <div className="ticker-bar__divider" aria-hidden="true" />

      {/* Scrolling tape */}
      <div className="ticker-bar__track" aria-hidden="true">
        <div className="ticker-bar__tape">
          {tape.map((item, index) => {
            const isPositive = (item.change_percent ?? 0) >= 0;
            const changeStr = item.change_percent != null
              ? `(${isPositive ? '+' : ''}${item.change_percent.toFixed(2)}%)`
              : '(—)';
            const priceStr = item.last_price != null
              ? item.last_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })
              : '—';

            return (
              <span key={`${item.symbol}-${index}`} className="ticker-bar__item">
                {/* Figma: vertical separator line before each item */}
                <span className="ticker-bar__sep" aria-hidden="true" />
                {/* Figma: symbol label – Manrope Bold 17.08px white */}
                <strong className="ticker-bar__symbol">{item.symbol}</strong>
                {/* Figma: price + change – Segoe UI Semibold 17.08px */}
                <span className={`ticker-bar__price ${isPositive ? 'positive' : 'negative'}`}>
                  {priceStr} {changeStr}
                </span>
              </span>
            );
          })}
        </div>
      </div>
    </section>
  );
};
