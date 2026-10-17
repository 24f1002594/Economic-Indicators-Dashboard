import React from 'react';
import './KPISubCard.css';

interface KPISubCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaPositive?: boolean;
  /** PNG/JPG asset path (relative to public/). Takes priority over icon. */
  imageSrc?: string;
  /** CSS object-position for sprite sheets (e.g. '0% 50%' for left half) */
  imageObjectPosition?: string;
  /** Fallback ReactNode icon (used only when imageSrc is not provided) */
  icon?: React.ReactNode;
  flagMode?: boolean;
  /** Optional explicit card background override (for India vs World tint) */
  cardBg?: string;
}

export const KPISubCard: React.FC<KPISubCardProps> = ({
  label,
  value,
  delta,
  deltaPositive = true,
  imageSrc,
  imageObjectPosition = '50% 50%',
  icon,
  flagMode = false,
  cardBg,
}) => {
  // Strip any leading "▲ " or "▼ " prefix from the delta — the triangle is
  // rendered as a separate SVG element to match the Figma design exactly.
  const deltaText = delta ? delta.replace(/^[▲▼]\s*/, '') : undefined;

  // Long formatted values (e.g. "₹53.47 L Cr") don't fit the card at the
  // Figma-spec 36px, so scale the value down a touch once it gets long.
  const valueClassName = `kpi-sub-card__value${value.length > 8 ? ' kpi-sub-card__value--compact' : ''}`;

  const deltaBadge = deltaText && (
    <span
      className={`kpi-sub-card__delta ${deltaPositive ? 'positive' : 'negative'}`}
      aria-label={`${deltaPositive ? 'up' : 'down'} ${deltaText}`}
    >
      {/* Figma polygon-1 / polygon-12 SVG arrow */}
      <svg
        className="kpi-sub-card__delta-arrow"
        width="10"
        height="11"
        viewBox="0 0 10 11"
        fill="none"
        aria-hidden="true"
      >
        {deltaPositive ? (
          <path d="M5 1L9.33 9H0.67L5 1Z" fill="currentColor" />
        ) : (
          <path d="M5 10L0.67 2H9.33L5 10Z" fill="currentColor" />
        )}
      </svg>
      {deltaText}
    </span>
  );

  return (
    <div
      className={`kpi-sub-card${flagMode ? ' kpi-sub-card--flag' : ''}`}
      role="group"
      aria-label={label}
      style={cardBg ? { background: cardBg } : undefined}
    >
      {/* Figma: soft gradient glow (transparent → #1a3a46) behind the delta
          badge, extending toward the card's right edge */}
      <span className="kpi-sub-card__highlight" aria-hidden="true" />

      {/* Label row – flag mode: icon inline to the left of the label */}
      <div className="kpi-sub-card__header">
        {flagMode && imageSrc && (
          <span className="kpi-sub-card__flag-inline">
            <img src={imageSrc} alt="" aria-hidden="true" />
          </span>
        )}
        <span className="kpi-sub-card__label">{label}</span>
      </div>

      {/* Flag mode: value + delta sit inline on the same row.
          Illustration mode: value and delta stack on separate lines. */}
      {flagMode ? (
        <div className="kpi-sub-card__value-row">
          <strong className={valueClassName} aria-label={value}>
            {value}
          </strong>
          {deltaBadge}
        </div>
      ) : (
        <>
          <strong className={valueClassName} aria-label={value}>
            {value}
          </strong>
          {deltaBadge}
        </>
      )}

      {/* Illustration: bottom-right (not flag mode) */}
      {!flagMode && imageSrc && (() => {
        const isSprite = imageObjectPosition !== '50% 50%';
        const spriteDir = imageObjectPosition === '0% 50%' ? 'left' : 'right';
        return (
          <div
            className="kpi-sub-card__icon kpi-sub-card__icon--img"
            data-sprite={isSprite ? spriteDir : undefined}
          >
            <img
              src={imageSrc}
              alt=""
              aria-hidden="true"
              className={`kpi-sub-card__img${isSprite ? ' kpi-sub-card__img--sprite' : ''}`}
            />
          </div>
        );
      })()}
      {!flagMode && !imageSrc && icon && (
        <div className="kpi-sub-card__icon kpi-sub-card__icon--illustration">
          {icon}
        </div>
      )}
    </div>
  );
};
