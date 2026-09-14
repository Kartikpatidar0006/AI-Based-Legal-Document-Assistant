/**
 * LoadingSpinner — simple CSS-animated ring.
 * Pass size="sm" for a small inline spinner, default is standard.
 */

export default function LoadingSpinner({ size = 'md', label = 'Loading…' }) {
  return (
    <div
      className={`loading-spinner${size === 'sm' ? ' loading-spinner--sm' : ''}`}
      role="status"
      aria-label={label}
    >
      <div className="loading-spinner__ring" />
      {label && <span className="loading-spinner__label">{label}</span>}
    </div>
  );
}
