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
import { getDocument, analyzeDocument, askQuery, askDocumentQuestion } from '../api';
import RiskBadge from '../components/common/RiskBadge';
import SourceChip from '../components/common/SourceChip';
import LoadingSpinner from '../components/common/LoadingSpinner';
import AudioWalkthrough from '../components/common/AudioWalkthrough';

/* ── Constants ──────────────────────────────────────────────────────────────── */
const TABS = ['Summary', 'Clauses', 'Risk Analysis'];

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
function QAPanel({ doc, className = '' }) {
  const [history, setHistory]   = useState([]);
  const [question, setQuestion] = useState('');
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
    e?.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError('');
    const optimisticEntry = { question: q, answer: null, sources: [], chunks_used: null, isDocQA: !!doc?.id };
    setHistory((prev) => [...prev, optimisticEntry]);
    setQuestion('');

    try {
      if (doc?.id) {
        const priorTurns = history.filter((h) => h.answer);
        const result = await askDocumentQuestion(doc.id, q, priorTurns);
        setHistory((prev) => [
          ...prev.slice(0, -1),
          {
            question: q,
            answer: result.answer,
            filename: result.filename || doc.filename,
            disclaimer: result.disclaimer,
            isDocQA: true,
          },
        ]);
      } else {
        const result = await askQuery(q, null);
        setHistory((prev) => [
          ...prev.slice(0, -1),
          {
            question: q,
            answer: result.answer,
            sources: result.sources || [],
            chunks_used: result.chunks_used,
            isDocQA: false,
          },
        ]);
      }
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
    <aside className={`qa-panel ${className}`.trim()} aria-label="Ask a question about this document">
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

      {/* Document scope indicator */}
      <div className="qa-doc-scope-bar">
        <span className="qa-doc-scope-tag">Contract Scope</span>
        <span className="qa-doc-scope-filename" title={doc?.filename || 'Active Document'}>
          📄 {doc?.filename || 'Document Text'}
        </span>
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
            <p className="qa-empty__heading">Ask about this contract</p>
            <p className="qa-empty__sub">
              Questions are answered directly from <strong>{doc?.filename || 'this document'}</strong>. Try one of these:
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
                  {item.isDocQA ? (
                    <span className="qa-chunks-tag qa-chunks-tag--doc">
                      Document Grounded
                    </span>
                  ) : item.chunks_used != null ? (
                    <span className="qa-chunks-tag">
                      {item.chunks_used} passage{item.chunks_used !== 1 ? 's' : ''}
                    </span>
                  ) : null}
                </span>
                <div className="qa-message__bubble">
                  {renderAnswer(item.answer)}

                  {/* Sources for general query fallback */}
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

                  {/* Grounded document indicator for doc QA */}
                  {item.isDocQA && item.filename && (
                    <div className="qa-sources" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--panel-border)' }}>
                      <div className="qa-sources__label">Source Document</div>
                      <div className="qa-sources__list">
                        <div className="qa-source-item">
                          <span className="qa-source-item__icon" aria-hidden="true">📄</span>
                          <span className="qa-source-item__name" title={item.filename}>
                            {item.filename}
                          </span>
                          <span className="qa-source-item__score" style={{ background: 'rgba(13, 148, 136, 0.12)', color: 'var(--color-teal)' }}>
                            100% doc match
                          </span>
                        </div>
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
            <span className="qa-loading-text">Analyzing {doc?.filename || 'document'} text…</span>
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
  const [mobilePane, setMobilePane] = useState('analysis'); // 'analysis' | 'qa'
  const [showQAPanel, setShowQAPanel] = useState(true);

  const loadDoc = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getDocument(id);
      // Merge the cached analysis fields (summary_result, clause_result, risk_result)
      // that GET /documents/{id} now returns directly from the DB.
      // This means WorkspaceDocPage never needs to call /analyze on its own
      // for a document that is already status=ready.
      setDoc(data);
      // Auto-select Risk Analysis tab if there are flagged issues
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
      // Merge the fresh analysis into doc state so tabs render immediately
      setDoc((prev) => ({
        ...prev,
        status: 'ready',
        summary_result: result.summary_result,
        clause_result:  result.clause_result,
        risk_result:    result.risk_result,
      }));
      if (result.risk_result?.total_issues_found > 0) {
        setActiveTab('Risk Analysis');
      }
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

  // hasAnalysis: true when the server has returned cached analysis data.
  // This is populated directly by GET /documents/{id} for status=ready docs,
  // so the "Run Analysis Now" button never shows for already-analyzed documents.
  const hasAnalysis = !!(doc?.summary_result || doc?.clause_result || doc?.risk_result);

  // Show the analyze prompt only when the document is NOT ready and has no cached data.
  const showAnalyzePrompt = !hasAnalysis && doc?.status !== 'ready';

  // Show a repair prompt when status=ready but cached analysis is missing.
  // This indicates a previous analysis worker crashed after updating status
  // but before persisting the JSONB results. The backend handles re-analysis.
  const showRepairPrompt = !hasAnalysis && doc?.status === 'ready';

  return (
    <div className={`workspace-doc${!showQAPanel ? ' workspace-doc--full' : ''}`}>
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

        {/* Mobile / Narrow screen pane switch tabs (≤ 900px) */}
        <div className="doc-pane-tabs" role="tablist" aria-label="Switch between document and Q&A">
          <button
            type="button"
            className={`doc-pane-tab ${mobilePane === 'analysis' ? 'doc-pane-tab--active' : ''}`}
            onClick={() => setMobilePane('analysis')}
            aria-selected={mobilePane === 'analysis'}
          >
            📄 Analysis
          </button>
          <button
            type="button"
            className={`doc-pane-tab ${mobilePane === 'qa' ? 'doc-pane-tab--active' : ''}`}
            onClick={() => setMobilePane('qa')}
            aria-selected={mobilePane === 'qa'}
          >
            ⚖ Ask Q&A
          </button>
        </div>

        <div className="doc-header-bar__actions">
          {doc?.risk_result?.overall_risk_score && (
            <RiskBadge level={doc.risk_result.overall_risk_score} />
          )}

          {/* Desktop Q&A panel toggle button */}
          <button
            type="button"
            className={`doc-qa-toggle-btn ${showQAPanel ? 'doc-qa-toggle-btn--active' : ''}`}
            onClick={() => setShowQAPanel((v) => !v)}
            title={showQAPanel ? 'Hide Q&A sidebar' : 'Show Q&A sidebar'}
            aria-label={showQAPanel ? 'Hide Q&A sidebar' : 'Show Q&A sidebar'}
          >
            <span aria-hidden="true">💬</span>
            <span className="doc-qa-toggle-text">{showQAPanel ? 'Hide Q&A' : 'Ask Q&A'}</span>
          </button>
        </div>
      </header>

      {/* ── Left: Analysis panel ──────────────────────────────────────── */}
      <main
        className={`analysis-panel ${mobilePane !== 'analysis' ? 'analysis-panel--mobile-hidden' : ''}`}
        id="analysis-panel"
        aria-label="Document analysis"
      >

        {/* Not-yet-analyzed — only shown for pending/error docs with no cached data */}
        {showAnalyzePrompt && (
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

        {/* Repair prompt — status=ready but cached analysis is missing (crashed worker) */}
        {showRepairPrompt && (
          <div className="not-analyzed-notice">
            <p style={{ marginBottom: '8px' }}>
              <strong>Analysis incomplete</strong>
            </p>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted, #888)', marginBottom: '16px' }}>
              This document was marked as ready but its analysis data is missing,
              likely due to a server interruption. Click below to repair it.
            </p>
            {analyzeError && <div className="form-error" role="alert">{analyzeError}</div>}
            <button
              id="repair-analysis-btn"
              className="btn btn--primary"
              onClick={handleRunAnalysis}
              disabled={analyzing}
            >
              {analyzing ? 'Repairing… (up to 30 s)' : 'Repair Analysis'}
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
                <SummarySection summaryResult={doc?.summary_result} documentId={id || doc?.id} />
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
      {showQAPanel && (
        <QAPanel
          doc={doc}
          className={mobilePane !== 'qa' ? 'qa-panel--mobile-hidden' : ''}
        />
      )}
    </div>
  );
}
