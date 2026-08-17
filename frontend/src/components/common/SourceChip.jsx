/**
 * SourceChip — small citation chip used in both the Risk Analysis section
 * (RAG sources) and the Query page (source documents).
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
      <span className="source-chip__name">{filename}</span>
      {category && (
        <span className="source-chip__category">{category}</span>
      )}
      {similarityScore != null && (
        <span className="source-chip__score">
          {Math.round(similarityScore * 100)}% match
        </span>
      )}
    </span>
  );
}
