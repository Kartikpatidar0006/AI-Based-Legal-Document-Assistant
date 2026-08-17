/**
 * QueryPage — Ask a legal question against the RAG knowledge base.
 *
 * Maintains a session-local history of Q&A pairs (cleared on page refresh).
 * Each answer includes a "Sources" section with SourceChip citations.
 * Category filter: All | Templates | Compliance Docs
 */

import { useState, useRef, useEffect } from 'react';
import { askQuery } from '../api';
import SourceChip from '../components/common/SourceChip';
import LoadingSpinner from '../components/common/LoadingSpinner';

const CATEGORY_OPTIONS = [
  { value: '',                label: 'All Documents' },
  { value: 'templates',       label: 'Contract Templates' },
  { value: 'compliance_docs', label: 'Compliance Docs' },
];

export default function QueryPage() {
  const [history, setHistory]     = useState([]); // [{question, answer, sources, chunks_used}]
  const [question, setQuestion]   = useState('');
  const [category, setCategory]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');

  const bottomRef = useRef(null);

  // Auto-scroll to newest answer
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  async function handleSubmit(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;

    setLoading(true);
    setError('');
    try {
      const result = await askQuery(q, category || null);
      setHistory((prev) => [...prev, {
        question: q,
        answer:   result.answer,
        sources:  result.sources || [],
        chunks_used: result.chunks_used,
      }]);
      setQuestion('');
    } catch (err) {
      setError(err.message || 'Failed to get an answer. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  // Allow Shift+Enter for newlines, Enter to submit
  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  // Split answer text on newlines for readable rendering
  function renderAnswer(text) {
    return (text || '').split('\n').filter((l) => l.trim()).map((line, i) => (
      <p key={i}>{line}</p>
    ));
  }

  return (
    <div className="page query-page">
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Ask a Legal Question</h1>
          <p className="page-subtitle">
            Ask anything about Indian business law, contract clauses, or compliance.
            Answers are drawn from our curated legal knowledge base.
          </p>
        </div>
      </div>

      {/* ── Q&A history ──────────────────────────────────────────────────── */}
      <div className="qa-history" aria-live="polite" aria-label="Conversation history">
        {history.length === 0 && !loading && (
          <div className="query-empty">
            <span className="query-empty__icon" aria-hidden="true">💬</span>
            <p className="query-empty__text">
              Ask a question to get started. For example: <em>"What should I look for in an NDA?"</em>
              or <em>"Is a non-compete clause enforceable in India?"</em>
            </p>
          </div>
        )}

        {history.map((item, i) => (
          <div key={i} className="qa-pair">
            {/* Question bubble */}
            <div className="qa-question">
              <span className="qa-question__label" aria-hidden="true">You</span>
              <div className="qa-question__text">{item.question}</div>
            </div>

            {/* Answer block */}
            <div className="qa-answer">
              <div className="qa-answer__header">
                <span className="qa-answer__label" aria-hidden="true">
                  <span className="qa-answer__logo-mark">⚖</span> LegalEase AI
                </span>
                {item.chunks_used != null && (
                  <span className="qa-answer__chunks">
                    {item.chunks_used} passage{item.chunks_used !== 1 ? 's' : ''} referenced
                  </span>
                )}
              </div>
              <div className="qa-answer__text">
                {renderAnswer(item.answer)}
              </div>

              {/* Sources */}
              {item.sources && item.sources.length > 0 && (
                <div className="qa-sources">
                  <p className="qa-sources__label">Sources</p>
                  <div className="qa-sources__chips">
                    {item.sources.map((src, j) => (
                      <SourceChip
                        key={j}
                        filename={src.filename}
                        category={src.category}
                        similarityScore={src.similarity_score}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator while waiting for answer */}
        {loading && (
          <div className="qa-loading">
            <LoadingSpinner size="sm" label="Searching knowledge base…" />
          </div>
        )}

        {error && (
          <div className="qa-error form-error" role="alert">{error}</div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ───────────────────────────────────────────────────── */}
      <div className="query-input-area">
        <form id="query-form" className="query-form" onSubmit={handleSubmit}>
          <select
            id="category-filter"
            className="form-input form-select query-form__category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Filter by document category"
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <textarea
            id="question-input"
            className="form-input query-form__textarea"
            placeholder="Ask a legal question… (Enter to send, Shift+Enter for new line)"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={loading}
          />

          <button
            id="query-submit-btn"
            type="submit"
            className="btn btn--primary query-form__submit"
            disabled={loading || !question.trim()}
            aria-label="Ask question"
          >
            {loading ? '…' : '→'}
          </button>
        </form>
        <p className="query-disclaimer">
          AI-generated answers may not be legally accurate. Consult a qualified lawyer for advice specific to your situation.
        </p>
      </div>
    </div>
  );
}
