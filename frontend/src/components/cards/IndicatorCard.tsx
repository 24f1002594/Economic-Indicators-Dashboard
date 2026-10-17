import React from 'react';
import './IndicatorCard.css';

interface IndicatorCardProps {
  title: string;
  subtitle?: string;
  subtitleColor?: 'cyan' | 'amber';
  animationDelay?: number;
  ariaLabel?: string;
  source?: { name: string; source_url: string };
  asOfDate?: string | null;
  freshnessStatus?: string;
  message?: string | null;
  children: React.ReactNode;
}

export const IndicatorCard: React.FC<IndicatorCardProps> = ({
  title,
  subtitle,
  subtitleColor = 'cyan',
  animationDelay = 0,
  ariaLabel,
  source,
  asOfDate,
  freshnessStatus,
  message,
  children,
}) => {
  return (
    <section
      className="indicator-card indicator-card--visible"
      role="region"
      aria-label={ariaLabel ?? title}
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {/* Figma: top-left teal glow ellipse */}
      <div className="indicator-card__ellipse indicator-card__ellipse--tl" aria-hidden="true" />
      {/* Figma: bottom-right teal glow ellipse */}
      <div className="indicator-card__ellipse indicator-card__ellipse--br" aria-hidden="true" />

      {/* Glassmorphism border highlight */}
      <div className="indicator-card__border-highlight" aria-hidden="true" />

      {/* Figma: glossy silver "folded corner" accent, clipped by the card's
          own top-left rounded corner (Vector 1624/1625 in the design) */}
      <img
        className="indicator-card__corner-fold"
        src="/figma-assets/corner-fold.svg"
        alt=""
        aria-hidden="true"
      />

      {/* Figma: dark header bar – rgba(44,44,45,0.6) */}
      <header className="indicator-card__header" aria-label={ariaLabel ?? title}>
        <h2 className="indicator-card__title">
          {title}
          {subtitle && (
            <em
              className={`indicator-card__subtitle indicator-card__subtitle--${subtitleColor}`}
            >
              {' '}{subtitle}
            </em>
          )}
        </h2>
      </header>

      {/* Card Body */}
      <div className="indicator-card__body">
        {children}
        {source && (
          <footer className="indicator-card__source">
            <span
              className={`indicator-card__source-dot indicator-card__source-dot--${freshnessStatus ?? 'unavailable'}`}
              aria-hidden="true"
            />
            <span className="indicator-card__source-text">
              <span className="sr-only">{freshnessStatus ?? 'unavailable'} · </span>
              Source: <a href={source.source_url} target="_blank" rel="noreferrer">{source.name}</a>
              {asOfDate ? ` · As of ${asOfDate}` : ''}
              {message ? ` — ${message}` : ''}
            </span>
          </footer>
        )}
      </div>
    </section>
  );
};
