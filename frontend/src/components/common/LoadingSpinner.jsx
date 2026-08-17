/**
 * LoadingSpinner — simple CSS-animated ring.
 * Pass size="sm" for a small inline spinner, default is standard.
 */

export default function LoadingSpinner({ size = 'md', label = 'Loading…' }) {
  return (
    <div className={`spinner-wrap spinner-wrap--${size}`} role="status" aria-label={label}>
      <div className="spinner" />
      {label && <span className="spinner-label">{label}</span>}
    </div>
  );
}
