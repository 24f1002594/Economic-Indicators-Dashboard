import React from 'react';
import './Skeleton.css';

export const SkeletonCard: React.FC = () => (
  <div className="skeleton-card" aria-hidden="true">
    <div className="skeleton-card__title skeleton-shimmer" />
    <div className="skeleton-card__kpi-row">
      <div className="skeleton-card__kpi skeleton-shimmer" />
      <div className="skeleton-card__kpi skeleton-shimmer" />
    </div>
    <div className="skeleton-card__chart skeleton-shimmer" />
  </div>
);

export const SkeletonGrid: React.FC = () => (
  <main className="dashboard-grid" aria-label="Loading dashboard">
    {Array.from({ length: 6 }, (_, i) => (
      <SkeletonCard key={i} />
    ))}
  </main>
);
