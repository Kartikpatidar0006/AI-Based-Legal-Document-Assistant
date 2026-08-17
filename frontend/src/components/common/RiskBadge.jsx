/**
 * RiskBadge — colored pill showing High / Medium / Low risk level.
 * Colors follow the project design token system:
 *   High   → #D64550 (red)
 *   Medium → #F9A826 (amber-gold)
 *   Low    → #00A896 (teal)
 */

export default function RiskBadge({ level }) {
  const normalized = (level || '').toLowerCase();
  let cls = 'risk-badge';
  if (normalized === 'high')   cls += ' risk-badge--high';
  if (normalized === 'medium') cls += ' risk-badge--medium';
  if (normalized === 'low')    cls += ' risk-badge--low';

  return <span className={cls}>{level || 'Unknown'}</span>;
}
