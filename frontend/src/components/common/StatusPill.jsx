/**
 * StatusPill — document processing status indicator.
 *   uploaded → muted gray (document received, not yet analysed)
 *   analyzed → teal     (analysis complete)
 */

export default function StatusPill({ status }) {
  const normalized = (status || '').toLowerCase();
  let cls = 'status-pill';
  if (normalized === 'analyzed') cls += ' status-pill--analyzed';
  else                           cls += ' status-pill--uploaded';

  const label =
    normalized === 'analyzed' ? 'Analysed' :
    normalized === 'uploaded' ? 'Uploaded' :
    status || 'Unknown';

  return <span className={cls}>{label}</span>;
}
