/**
 * SourceChip — small citation chip for RAG sources in analysis and Q&A panels.
 *
 * Props:
 *   filename        — document filename
 *   category        — optional category label
 *   similarityScore — optional 0–1 float shown as a percentage
 */

export default function SourceChip({ filename, category, similarityScore }) {
  return (
    <span className="source-chip">
      <span className="source-chip__icon">📄</span>
      {filename}
      {category && (
        <span style={{ opacity: 0.6, marginLeft: 4 }}>· {category}</span>
      )}
      {similarityScore != null && (
        <span style={{ marginLeft: 4, fontWeight: 600, color: 'var(--color-primary-text)' }}>
          {Math.round(similarityScore * 100)}%
        </span>
      )}
    </span>
  );
}
