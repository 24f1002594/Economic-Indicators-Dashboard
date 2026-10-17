import React from 'react';
import './TitleBar.css';

interface TitleBarProps {
  onRefresh?: () => void;
  onSignOut?: () => void;
}

export const TitleBar: React.FC<TitleBarProps> = ({ onRefresh, onSignOut }) => {
  return (
    <header className="title-bar" role="banner">
      {/* Real candlestick chart background from Figma */}
      <div
        className="title-bar__bg"
        aria-hidden="true"
        style={{ backgroundImage: 'url(/figma-assets/header.png)' }}
      />
      <h1 className="title-bar__title">ECONOMIC INDICATOR</h1>
      <nav className="title-bar__nav" aria-label="Dashboard actions">
        {onRefresh && (
          <button
            className="title-bar__btn"
            aria-label="Refresh dashboard"
            onClick={onRefresh}
          >
            ↻ Refresh
          </button>
        )}
        {onSignOut && (
          <button
            className="title-bar__btn"
            onClick={onSignOut}
          >
            Sign out
          </button>
        )}
      </nav>
    </header>
  );
};
