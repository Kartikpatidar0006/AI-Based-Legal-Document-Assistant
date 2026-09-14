/**
 * WorkspaceDocPage.jsx — Split-pane document workspace.
 *
 * Replaces: DocumentAnalysisPage + QueryPage
 * Route: /workspace/:id
 *
 * Layout (desktop):
 *   Left column  — Document analysis: Summary / Clauses / Risk tabs
 *   Right column — Q&A chat panel: contextual questions about this document
 *
 * Layout (mobile): stacked vertically (analysis above, Q&A below)
 *
 * The Q&A panel seeds suggested questions from the document's flagged issues.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDocument, analyzeDocument, askQuery } from '../api';
import RiskBadge from '../components/common/RiskBadge';
import SourceChip from '../components/common/SourceChip';
import LoadingSpinner from '../components/common/LoadingSpinner';
import AudioWalkthrough from '../components/common/AudioWalkthrough';

/* ── Constants ──────────────────────────────────────────────────────────────── */
const TABS = ['Summary', 'Clauses', 'Risk Analysis'];

const CATEGORY_OPTIONS = [
  { value: '',                label: 'All' },
  { value: 'templates',       label: 'Templates' },
  { value: 'compliance_docs', label: 'Compliance' },
];

/* ── Analysis sub-sections ──────────────────────────────────────────────────── */
function SummarySection({ summaryResult, documentId }) {
  if (!summaryResult) {
    return <p className="section-empty">No summary available.</p>;
  }
  const { summary, key_points } = summaryResult;
  const paragraphs = (summary || '').split('\n').filter((l) => l.trim());

  return (
    <div>
      <div className="summary-text">
        {paragraphs.map((para, i) => <p key={i}>{para}</p>)}
      </div>
      <AudioWalkthrough documentId={documentId} />
      {key_points && key_points.length > 0 && (
        <div className="key-points">
          <h3 className="key-points__heading">Key Points</h3>
          <ul className="key-points__list">
            {key_points.map((point, i) => (
              <li key={i} className="key-points__item">{point}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ClausesSection({ clauseResult }) {
  if (!clauseResult || !clauseResult.clauses?.length) {
    return <p className="section-empty">No clauses were identified in this document.</p>;
  }
  return (
    <div>
      <p className="clause-count">
        {clauseResult.total_clauses_found} clause{clauseResult.total_clauses_found !== 1 ? 's' : ''} identified
      </p>
      <div className="clause-list">
        {clauseResult.clauses.map((clause, i) => (
          <div key={i} className="clause-card">
            <div className="clause-card__header">
              <span className="clause-tag">{clause.clause_type}</span>
              {clause.clause_number_or_location && (
                <span className="clause-location">{clause.clause_number_or_location}</span>
              )}
            </div>
            <p className="clause-text">{clause.clause_text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function RiskSection({ riskResult }) {
  if (!riskResult) {
    return <p className="section-empty">No risk analysis available.</p>;
  }
  const { overall_risk_score, flagged_issues, total_issues_found, rag_sources_used, disclaimer } = riskResult;
  const scoreClass =
    overall_risk_score?.toLowerCase() === 'high'   ? 'risk-score--high'   :
    overall_risk_score?.toLowerCase() === 'medium' ? 'risk-score--medium' :
    overall_risk_score?.toLowerCase() === 'low'    ? 'risk-score--low'    : '';

  return (
    <div>
      <div className={`risk-score-banner ${scoreClass}`}>
        <div>
          <div className="risk-score-banner__label">Overall Risk</div>
          <div className="risk-score-banner__value">{overall_risk_score || 'Unknown'}</div>
        </div>
        <span className="risk-score-banner__count">
          {total_issues_found} issue{total_issues_found !== 1 ? 's' : ''} found
        </span>
      </div>

      {flagged_issues && flagged_issues.length > 0 && (
        <div className="flagged-issues">
          <h3 className="flagged-issues__heading">Flagged Issues</h3>
          {flagged_issues.map((issue, i) => (
            <div key={i} className="issue-card">
              <div className="issue-card__header">
                <RiskBadge level={issue.risk_level} />
                <span className="issue-card__clause-type">{issue.clause_type}</span>
              </div>
              <div className="issue-card__body">
                <div className="issue-card__field">
                  <span className="issue-card__field-label">Issue</span>
                  <p className="issue-card__field-text">{issue.issue_description}</p>
                </div>
                <div className="issue-card__field">
                  <span className="issue-card__field-label">What to do</span>
                  <p className="issue-card__field-text issue-card__recommendation">{issue.recommendation}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {flagged_issues && flagged_issues.length === 0 && (
        <div className="no-issues">
          <span className="no-issues__icon">✓</span>
          No significant risk issues were flagged in this document.
        </div>
      )}

      {rag_sources_used && rag_sources_used.length > 0 && (
        <div className="rag-sources">
          <p className="rag-sources__label">Analysis compared against:</p>
          <div className="rag-sources__chips">
            {rag_sources_used.map((src, i) => <SourceChip key={i} filename={src} />)}
          </div>
        </div>
      )}

      {disclaimer && <p className="analysis-disclaimer">{disclaimer}</p>}
    </div>
  );
}

/* ── Q&A Panel ──────────────────────────────────────────────────────────────── */
function QAPanel({ doc }) {
  const [history, setHistory]   = useState([]);
  const [question, setQuestion] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  // Build suggested questions from doc's flagged issues (or fallback to generic ones)
  const suggestions = (() => {
    const issues = doc?.risk_result?.flagged_issues || [];
    if (issues.length > 0) {
      return issues.slice(0, 3).map((issue) =>
        `What are the implications of the "${issue.clause_type}" clause in this contract?`
      );
    }
    return [
      'What are the key risks in this document?',
      'Summarize the main obligations of each party.',
      'Are there any unusual or one-sided clauses?',
    ];
  })();

  async function handleSubmit(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError('');
    const optimisticEntry = { question: q, answer: null, sources: [], chunks_used: null };
    setHistory((prev) => [...prev, optimisticEntry]);
    setQuestion('');

    try {
      const result = await askQuery(q, category || null);
      setHistory((prev) => [
        ...prev.slice(0, -1),
        { question: q, answer: result.answer, sources: result.sources || [], chunks_used: result.chunks_used },
      ]);
    } catch (err) {
      setHistory((prev) => prev.slice(0, -1));
      setError(err.message || 'Failed to get an answer. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  function handleSuggestion(text) {
    setQuestion(text);
    textareaRef.current?.focus();
  }

  function renderAnswer(text) {
    return (text || '').split('\n').filter((l) => l.trim()).map((line, i) => (
      <p key={i}>{line}</p>
    ));
  }

  return (
    <aside className="qa-panel" aria-label="Ask a question about this document">
      {/* Header */}
      <div className="qa-panel__header">
        <div className="qa-panel__title">
          <span className="qa-panel__title-icon" aria-hidden="true">⚖</span>
          Ask a Question
        </div>
        {history.length > 0 && (
          <button
            className="qa-panel__clear-btn"
            onClick={() => { setHistory([]); setError(''); }}
            aria-label="Clear conversation"
          >
            Clear
          </button>
        )}
      </div>

      {/* Category filter pills */}
      <div className="qa-category-row" role="group" aria-label="Filter by category">
        {CATEGORY_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`qa-category-pill${category === opt.value ? ' qa-category-pill--active' : ''}`}
            onClick={() => setCategory(opt.value)}
            aria-pressed={category === opt.value}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Chat history */}
      <div
        className="qa-history"
        role="log"
        aria-live="polite"
        aria-label="Conversation"
      >
        {/* Empty state with suggested questions */}
        {history.length === 0 && !loading && (
          <div className="qa-empty">
            <div className="qa-empty__icon" aria-hidden="true">💬</div>
            <p className="qa-empty__heading">Ask about this document</p>
            <p className="qa-empty__sub">
              Get grounded answers drawn from the knowledge base. Try one of these:
            </p>
            <div className="qa-empty__suggestions">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  className="qa-suggestion"
                  onClick={() => handleSuggestion(s)}
                  aria-label={`Use suggestion: ${s}`}
                >
                  <span className="qa-suggestion__text">{s}</span>
                  <span className="qa-suggestion__arrow" aria-hidden="true">→</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {history.map((item, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* User message */}
            <div className="qa-message qa-message--user">
              <span className="qa-message__sender">You</span>
              <div className="qa-message__bubble">{item.question}</div>
            </div>

            {/* AI answer */}
            {item.answer !== null && (
              <div className="qa-message qa-message--ai">
                <span className="qa-message__sender">
                  <span className="qa-message__sender-logo" aria-hidden="true">⚖</span>
                  LegalEase AI
                  {item.chunks_used != null && (
                    <span className="qa-chunks-tag">
                      {item.chunks_used} passage{item.chunks_used !== 1 ? 's' : ''}
                    </span>
                  )}
                </span>
                <div className="qa-message__bubble">
                  {renderAnswer(item.answer)}
                  {/* Sources */}
                  {item.sources && item.sources.length > 0 && (
                    <div className="qa-sources" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--panel-border)' }}>
                      <div className="qa-sources__label">Grounded in</div>
                      <div className="qa-sources__list">
                        {item.sources.map((src, j) => (
                          <div key={j} className="qa-source-item">
                            <span className="qa-source-item__icon" aria-hidden="true">📄</span>
                            <span className="qa-source-item__name" title={src.filename}>
                              {src.filename}
                            </span>
                            {src.similarity_score != null && (
                              <span className="qa-source-item__score">
                                {Math.round(src.similarity_score * 100)}%
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Loading dots */}
        {loading && (
          <div className="qa-loading" aria-live="polite" aria-label="Generating answer…">
            <div className="qa-loading-dots" aria-hidden="true">
              <span /><span /><span />
            </div>
            <span className="qa-loading-text">Searching knowledge base…</span>
          </div>
        )}

        {error && (
          <div className="qa-error" role="alert">{error}</div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="qa-input-area">
        <form id="qa-form" className="qa-form" onSubmit={handleSubmit}>
          <label htmlFor="qa-input" className="sr-only">Ask a legal question</label>
          <textarea
            id="qa-input"
            ref={textareaRef}
            className="qa-textarea"
            placeholder="Ask a legal question… (Enter to send, Shift+Enter for new line)"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={loading}
          />
          <button
            id="qa-submit-btn"
            type="submit"
            className="qa-submit"
            disabled={loading || !question.trim()}
            aria-label="Submit question"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </button>
        </form>
        <p className="qa-disclaimer">
          AI-generated answers may not be legally accurate. Consult a qualified lawyer for specific advice.
        </p>
      </div>
    </aside>
  );
}

/* ══════════════════════════════════════════════════════════════════════════════
   WorkspaceDocPage — main export
   ══════════════════════════════════════════════════════════════════════════════ */
export default function WorkspaceDocPage() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const [doc, setDoc]               = useState(null);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [activeTab, setActiveTab]   = useState('Summary');
  const [analyzing, setAnalyzing]   = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');

  const loadDoc = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getDocument(id);
      setDoc(data);
      // Auto-select Risk Analysis if it exists and has issues
      if (data?.risk_result?.total_issues_found > 0) {
        setActiveTab('Risk Analysis');
      }
    } catch (err) {
      setError(err.message || 'Failed to load document.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadDoc(); }, [loadDoc]);

  async function handleRunAnalysis() {
    setAnalyzing(true);
    setAnalyzeError('');
    try {
      const result = await analyzeDocument(id);
      setDoc((prev) => ({ ...prev, ...result, status: 'analyzed' }));
    } catch (err) {
      setAnalyzeError(err.message || 'Analysis failed. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  }

  /* ── Loading state ────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="workspace-doc" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="panel-loading">
          <LoadingSpinner label="Loading document…" />
        </div>
      </div>
    );
  }

  /* ── Error state ──────────────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="workspace-doc" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="panel-error">
          <div className="form-error" role="alert">{error}</div>
          <button className="btn btn--ghost" onClick={() => navigate('/workspace')}>
            ← Back to Workspace
          </button>
        </div>
      </div>
    );
  }

  const hasAnalysis = doc?.summary_result || doc?.clause_result || doc?.risk_result;

  return (
    <div className="workspace-doc">
      {/* ── Header bar (full width) ────────────────────────────────────── */}
      <header className="doc-header-bar">
        <button
          id="back-to-workspace-btn"
          className="doc-header-bar__back"
          onClick={() => navigate('/workspace')}
          aria-label="Back to workspace"
          title="Back to workspace"
        >
          ←
        </button>

        <div className="doc-header-bar__icon" aria-hidden="true">📄</div>

        <div className="doc-header-bar__info">
          <span className="doc-header-bar__name" title={doc?.filename}>
            {doc?.filename}
          </span>
          {doc?.document_type && (
            <span className="doc-header-bar__type">{doc.document_type}</span>
          )}
        </div>

        <div className="doc-header-bar__actions">
          {doc?.risk_result?.overall_risk_score && (
            <RiskBadge level={doc.risk_result.overall_risk_score} />
          )}
        </div>
      </header>

      {/* ── Left: Analysis panel ──────────────────────────────────────── */}
      <main className="analysis-panel" id="analysis-panel" aria-label="Document analysis">

        {/* Not-yet-analyzed */}
        {!hasAnalysis && (
          <div className="not-analyzed-notice">
            <p>This document hasn't been analysed yet.</p>
            {analyzeError && <div className="form-error" role="alert">{analyzeError}</div>}
            <button
              id="run-analysis-btn"
              className="btn btn--primary"
              onClick={handleRunAnalysis}
              disabled={analyzing}
            >
              {analyzing ? 'Analysing… (up to 30 s)' : 'Run Analysis Now'}
            </button>
          </div>
        )}

        {/* Tabs */}
        {hasAnalysis && (
          <>
            <div className="analysis-tabs" role="tablist" aria-label="Analysis sections">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  id={`tab-${tab.toLowerCase().replace(' ', '-')}`}
                  role="tab"
                  aria-selected={activeTab === tab}
                  className={`analysis-tab${activeTab === tab ? ' analysis-tab--active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab}
                  {tab === 'Risk Analysis' && doc?.risk_result?.overall_risk_score && (
                    <span
                      className={`tab-risk-dot tab-risk-dot--${doc.risk_result.overall_risk_score.toLowerCase()}`}
                      aria-hidden="true"
                    />
                  )}
                </button>
              ))}
            </div>

            <div
              role="tabpanel"
              className="analysis-content"
              aria-labelledby={`tab-${activeTab.toLowerCase().replace(' ', '-')}`}
            >
              {activeTab === 'Summary' && (
                <SummarySection summaryResult={doc?.summary_result} documentId={id} />
              )}
              {activeTab === 'Clauses' && (
                <ClausesSection clauseResult={doc?.clause_result} />
              )}
              {activeTab === 'Risk Analysis' && (
                <RiskSection riskResult={doc?.risk_result} />
              )}
            </div>
          </>
        )}
      </main>

      {/* ── Right: Q&A chat panel ─────────────────────────────────────── */}
      <QAPanel doc={doc} />
    </div>
  );
}
