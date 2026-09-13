/**
 * QueryPage — Ask a legal question against the RAG knowledge base.
 *
 * Maintains a session-local history of Q&A pairs (cleared on page refresh).
 * Each answer and its sources sit side-by-side in a two-column unit.
 *
 * Empty state: two-column layout — clickable suggestion prompts (left) +
 * a greyed knowledge-base preview rail (right) that teaches the product's
 * citation-grounding value before the user asks anything.
 *
 * Accepts router state from HomePage navigation:
 *   location.state.prefillQuestion — pre-fills the text input
 *   location.state.category        — pre-selects the category filter
 */

import { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { askQuery } from '../api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const CATEGORY_OPTIONS = [
  { value: '',                label: 'All Documents' },
  { value: 'templates',       label: 'Contract Templates' },
  { value: 'compliance_docs', label: 'Compliance Docs' },
];

// Each suggestion gets a category tag so the cards are visually distinct
const SUGGESTED_QUESTIONS = [
  { text: 'Is a non-compete clause enforceable in India?',          tag: 'Contracts' },
  { text: 'What does an NDA need to include to be legally valid?',  tag: 'NDAs' },
  { text: 'What are the MSME registration thresholds for 2024?',    tag: 'Compliance' },
];

// Knowledge base categories surfaced as tag pills in the empty state header
const KB_CATEGORIES = ['GST', 'MSME', 'Labour Law', 'Contracts', 'NDAs', 'IP Rights'];

export default function QueryPage() {
  const location = useLocation();

  const [history, setHistory]   = useState([]); // [{question, answer, sources, chunks_used}]
  const [question, setQuestion] = useState(() => location.state?.prefillQuestion || '');
  const [category, setCategory] = useState(() => location.state?.category        || '');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

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

  // Clicking a suggestion populates the composer — does NOT auto-submit
  function handleSuggestionClick(text) {
    setQuestion(text);
    document.getElementById('question-input')?.focus();
  }

  return (
    <div className="page query-page">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Ask a Legal Question</h1>
          <p className="page-subtitle">
            Grounded answers drawn from a curated knowledge base of Indian business law,
            contracts, and compliance documents — with source citations on every response.
          </p>
        </div>
      </div>

      {/* ── Q&A history ──────────────────────────────────────────────────── */}
      <div className="qa-history" aria-live="polite" aria-label="Conversation history">

        {/* ── Empty state — two-column: suggestions left, KB preview right ── */}
        {history.length === 0 && !loading && (
          <div className="query-empty">

            {/* Left column — intro, KB tags, suggestion cards */}
            <div className="query-empty__left">
              <div>
                <p className="query-empty__intro">Try one of these to get started</p>
                <p className="query-empty__intro-sub">
                  Your questions and answers will appear here. Click a suggestion to
                  populate the composer below.
                </p>
              </div>

              {/* Knowledge-base category pills — teaches the product scope */}
              <div className="query-empty__kb-tags" aria-label="Knowledge base covers">
                {KB_CATEGORIES.map((cat) => (
                  <span key={cat} className="query-empty__kb-tag">{cat}</span>
                ))}
              </div>

              {/* Suggestion cards — visually distinct via nth-child accent colors */}
              <div className="query-empty__prompts" role="list">
                {SUGGESTED_QUESTIONS.map(({ text, tag }, i) => (
                  <button
                    key={i}
                    className="query-empty__prompt"
                    onClick={() => handleSuggestionClick(text)}
                    aria-label={`Use suggestion: ${text}`}
                    role="listitem"
                  >
                    <span className="query-empty__prompt-body">
                      <span className="query-empty__prompt-text">{text}</span>
                      <span className="query-empty__prompt-tag">{tag}</span>
                    </span>
                    <span className="query-empty__prompt-arrow" aria-hidden="true">→</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right column — greyed preview of what a "Sources" panel looks like */}
            <div className="query-empty__sources-preview" aria-hidden="true">
              <div className="query-empty__sources-preview-label">Sources cited</div>
              <p className="query-empty__sources-preview-intro">
                Every answer references the exact passages it was drawn from — shown here.
              </p>
              <div className="query-empty__sources-preview-list">
                {[80, 74, 61].map((w, i) => (
                  <div key={i} className="query-empty__source-ghost">
                    <div className="query-empty__source-ghost-icon" />
                    <div className="query-empty__source-ghost-lines">
                      <div className="query-empty__source-ghost-line" />
                      <div className="query-empty__source-ghost-line query-empty__source-ghost-line--short" />
                    </div>
                    <div className="query-empty__source-ghost-score" />
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* ── Q&A pairs — answer + source rail as one unit ─────────────── */}
        {history.map((item, i) => (
          <div key={i} className="qa-pair">

            {/* Question — right-aligned tinted block, not a speech bubble */}
            <div className="qa-question">
              <span className="qa-question__label" aria-hidden="true">You</span>
              <div className="qa-question__text">{item.question}</div>
            </div>

            {/* Answer unit — two-column grid: body left, source rail right */}
            <div className="qa-answer-unit">
              {/* Answer body */}
              <div className="qa-answer">
                <div className="qa-answer__header">
                  <span className="qa-answer__label" aria-hidden="true">
                    <span className="qa-answer__logo-mark">⚖</span>
                    LegalEase AI
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
              </div>

              {/* Source rail — architecturally central, not an afterthought */}
              {item.sources && item.sources.length > 0 ? (
                <div className="qa-source-rail" aria-label="Sources used">
                  <div className="qa-source-rail__label">Grounded in</div>
                  <div className="qa-source-rail__list">
                    {item.sources.map((src, j) => (
                      <div key={j} className="qa-source-item">
                        <span className="qa-source-item__icon" aria-hidden="true">📄</span>
                        <div className="qa-source-item__body">
                          <span className="qa-source-item__name" title={src.filename}>
                            {src.filename}
                          </span>
                          <div className="qa-source-item__meta">
                            {src.category && (
                              <span>{src.category.replace(/_/g, ' ')}</span>
                            )}
                            {src.similarity_score != null && (
                              <span className="qa-source-item__score">
                                {Math.round(src.similarity_score * 100)}%
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                // Grid placeholder so answer expands to full width gracefully
                <div aria-hidden="true" />
              )}
            </div>

          </div>
        ))}

        {/* Loading indicator */}
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

      {/* ── Input composer — elevated, teal-focus, circular send button ──── */}
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
            className="query-form__submit"
            disabled={loading || !question.trim()}
            aria-label="Ask question"
          >
            {loading ? '…' : '→'}
          </button>
        </form>
        <p className="query-disclaimer">
          AI-generated answers may not be legally accurate. Consult a qualified lawyer
          for advice specific to your situation.
        </p>
      </div>

    </div>
  );
}
