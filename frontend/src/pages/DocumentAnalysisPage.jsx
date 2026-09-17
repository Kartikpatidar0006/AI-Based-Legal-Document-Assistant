/**
 * DocumentAnalysisPage — renders the full AI analysis for a document.
 *
 * Three tab sections:
 *   Summary     — summary text + key points list
 *   Clauses     — each clause with type tag, location, text
 *   Risk Analysis — overall score, flagged issues, RAG sources, disclaimer
 *
 * Fetches GET /documents/:id on mount (which includes the persisted analysis).
 * If the document is in "uploaded" (not yet analyzed) status, it shows a
 * prompt to trigger analysis from here too.
 */

import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDocument, analyzeDocument, askDocumentQuestion } from '../api';
import RiskBadge from '../components/common/RiskBadge';
import SourceChip from '../components/common/SourceChip';
import LoadingSpinner from '../components/common/LoadingSpinner';
import AudioWalkthrough from '../components/common/AudioWalkthrough';

const TABS = ['Summary', 'Clauses', 'Risk Analysis'];

// ── Sub-components ───────────────────────────────────────────────────────────

function SummarySection({ summaryResult, documentId }) {
  if (!summaryResult) return <p className="section-empty">No summary available.</p>;

  const { summary, key_points } = summaryResult;

  // Preserve newlines from the AI-generated summary text
  const paragraphs = (summary || '').split('\n').filter((l) => l.trim());

  return (
    <div className="analysis-section">
      <div className="summary-text">
        {paragraphs.map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      {/* Voice walkthrough — listen to AI summary read aloud */}
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
    <div className="analysis-section">
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
  if (!riskResult) return <p className="section-empty">No risk analysis available.</p>;

  const {
    overall_risk_score,
    flagged_issues,
    total_issues_found,
    rag_sources_used,
    disclaimer,
  } = riskResult;

  const scoreClass =
    overall_risk_score?.toLowerCase() === 'high'   ? 'risk-score--high'   :
    overall_risk_score?.toLowerCase() === 'medium' ? 'risk-score--medium' :
    overall_risk_score?.toLowerCase() === 'low'    ? 'risk-score--low'    : '';

  return (
    <div className="analysis-section">
      {/* Overall score banner */}
      <div className={`risk-score-banner ${scoreClass}`}>
        <div className="risk-score-banner__label">Overall Risk Level</div>
        <div className="risk-score-banner__value">{overall_risk_score || 'Unknown'}</div>
        <div className="risk-score-banner__count">
          {total_issues_found} issue{total_issues_found !== 1 ? 's' : ''} found
        </div>
      </div>

      {/* Flagged issues */}
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
                  <p className="issue-card__field-text issue-card__recommendation">
                    {issue.recommendation}
                  </p>
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

      {/* RAG sources — the key differentiator: grounded analysis */}
      {rag_sources_used && rag_sources_used.length > 0 && (
        <div className="rag-sources">
          <p className="rag-sources__label">Analysis compared against:</p>
          <div className="rag-sources__chips">
            {rag_sources_used.map((src, i) => (
              <SourceChip key={i} filename={src} />
            ))}
          </div>
        </div>
      )}

      {/* Disclaimer — calm legal footnote, not alarming */}
      {disclaimer && (
        <p className="analysis-disclaimer">{disclaimer}</p>
      )}
    </div>
  );
}

function DocumentQASession({ documentId, filename }) {
  const [history, setHistory]     = useState([]); // [{ question, answer, disclaimer }]
  const [question, setQuestion]   = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const bottomRef                 = useRef(null);
  const textareaRef               = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  const quickQuestions = [
    "What are the key risks in this document?",
    "Does this contract have a non-compete clause?",
    "Summarize the termination terms in this agreement",
  ];

  async function handleSubmit(e) {
    if (e) e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError('');
    const optimisticTurn = { question: q, answer: null };
    setHistory((prev) => [...prev, optimisticTurn]);
    setQuestion('');

    try {
      const res = await askDocumentQuestion(documentId, q, history);
      setHistory((prev) => [
        ...prev.slice(0, -1),
        { question: q, answer: res.answer, disclaimer: res.disclaimer },
      ]);
    } catch (err) {
      setHistory((prev) => prev.slice(0, -1));
      setError(err.message || 'Failed to get answer. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <section className="doc-qa-section" aria-label={`Ask questions about ${filename}`}>
      <div className="doc-qa-section__header">
        <div>
          <h3 className="doc-qa-section__title">
            <span className="doc-qa-section__icon" aria-hidden="true">💬</span>
            Ask About This Document
          </h3>
          <p className="doc-qa-section__subtitle">
            Ask specific questions grounded exclusively in <strong>{filename}</strong>.
          </p>
        </div>
        {history.length > 0 && (
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => { setHistory([]); setError(''); }}
          >
            Clear chat
          </button>
        )}
      </div>

      {history.length === 0 && !loading && (
        <div className="doc-qa-suggestions">
          <p className="doc-qa-suggestions__title">Suggested questions:</p>
          <div className="doc-qa-suggestions__grid">
            {quickQuestions.map((prompt, i) => (
              <button
                key={i}
                type="button"
                className="doc-qa-suggestion-btn"
                onClick={() => {
                  setQuestion(prompt);
                  textareaRef.current?.focus();
                }}
              >
                <span>{prompt}</span>
                <span aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* History turns */}
      {history.length > 0 && (
        <div className="doc-qa-thread" role="log" aria-live="polite">
          {history.map((turn, i) => (
            <div key={i} className="doc-qa-turn">
              <div className="doc-qa-turn__q">
                <span className="doc-qa-turn__label">You</span>
                <p className="doc-qa-turn__q-text">{turn.question}</p>
              </div>
              {turn.answer !== null && (
                <div className="doc-qa-turn__a">
                  <span className="doc-qa-turn__label doc-qa-turn__label--ai">
                    <span aria-hidden="true">⚖</span> LegalEase AI
                  </span>
                  <div className="doc-qa-turn__a-text">
                    {(turn.answer || '').split('\n').filter((l) => l.trim()).map((line, j) => (
                      <p key={j}>{line}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="doc-qa-loading">
              <LoadingSpinner label={`Searching ${filename}…`} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}

      {error && <div className="form-error" role="alert">{error}</div>}

      {/* Composer */}
      <form className="doc-qa-composer" onSubmit={handleSubmit}>
        <label htmlFor="doc-qa-input" className="sr-only">Ask a question about this document</label>
        <textarea
          id="doc-qa-input"
          ref={textareaRef}
          className="doc-qa-textarea"
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Ask about clauses, risks, or terms in ${filename}… (Enter to send, Shift+Enter for new line)`}
          disabled={loading}
        />
        <button
          type="submit"
          className="btn btn--primary doc-qa-send-btn"
          disabled={loading || !question.trim()}
          aria-label="Send question"
        >
          Ask
        </button>
      </form>

      <p className="doc-qa-disclaimer">
        Answers are generated based solely on this document's text. This is general information, not legal advice.
      </p>
    </section>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function DocumentAnalysisPage() {
  const { id }    = useParams();
  const navigate  = useNavigate();

  const [doc, setDoc]             = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [activeTab, setActiveTab] = useState('Summary');

  // For re-running analysis on a document that was uploaded but not yet analyzed
  const [analyzing, setAnalyzing]   = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const data = await getDocument(id);
        if (!cancelled) setDoc(data);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load document.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  async function handleRunAnalysis() {
    setAnalyzing(true);
    setAnalyzeError('');
    try {
      const result = await analyzeDocument(id);
      // Merge analysis result into doc state
      setDoc((prev) => ({ ...prev, ...result, status: 'analyzed' }));
    } catch (err) {
      setAnalyzeError(err.message || 'Analysis failed. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  }

  // ── Render states ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="page page--centered">
        <LoadingSpinner label="Loading document…" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page page--centered">
        <div className="page-error" role="alert">{error}</div>
        <button className="btn btn--ghost" onClick={() => navigate('/')}>← Back to Dashboard</button>
      </div>
    );
  }

  const hasAnalysis = doc?.summary_result || doc?.clause_result || doc?.risk_result;

  return (
    <div className="page">
      {/* ── Breadcrumb ─────────────────────────────────────────────────── */}
      <button
        id="back-to-dashboard-btn"
        className="btn btn--ghost btn--sm back-link"
        onClick={() => navigate('/')}
      >
        ← Dashboard
      </button>

      {/* ── Document header ────────────────────────────────────────────── */}
      <div className="doc-header">
        <div className="doc-header__meta">
          <div className="doc-header__icon-wrap" aria-hidden="true">📄</div>
          <div>
            <h1 className="doc-header__filename">{doc?.filename}</h1>
            {doc?.document_type && (
              <span className="doc-header__type">{doc.document_type}</span>
            )}
          </div>
        </div>

        {/* Overall risk score chip in header for quick reference */}
        {doc?.risk_result?.overall_risk_score && (
          <RiskBadge level={doc.risk_result.overall_risk_score} />
        )}
      </div>

      {/* ── Not-yet-analyzed state ────────────────────────────────────── */}
      {!hasAnalysis && (
        <div className="not-analyzed-notice">
          <p>This document has not been analysed yet.</p>
          {analyzeError && <div className="form-error">{analyzeError}</div>}
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

      {/* ── Analysis tabs ─────────────────────────────────────────────── */}
      {hasAnalysis && (
        <>
          <div className="tabs" role="tablist" aria-label="Analysis sections">
            {TABS.map((tab) => (
              <button
                key={tab}
                id={`tab-${tab.toLowerCase().replace(' ', '-')}`}
                role="tab"
                aria-selected={activeTab === tab}
                className={'tab-btn' + (activeTab === tab ? ' tab-btn--active' : '')}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
                {tab === 'Risk Analysis' && doc?.risk_result?.overall_risk_score && (
                  <span className={
                    'tab-risk-dot tab-risk-dot--' +
                    doc.risk_result.overall_risk_score.toLowerCase()
                  } />
                )}
              </button>
            ))}
          </div>

          <div role="tabpanel" className="tab-panel">
            {activeTab === 'Summary'      && <SummarySection summaryResult={doc?.summary_result} documentId={id || doc?.id} />}
            {activeTab === 'Clauses'      && <ClausesSection clauseResult={doc?.clause_result} />}
            {activeTab === 'Risk Analysis' && <RiskSection   riskResult={doc?.risk_result} />}
          </div>

          {/* ── Scoped Document Q&A Section ─────────────────────────────── */}
          <DocumentQASession documentId={id || doc?.id} filename={doc?.filename} />
        </>
      )}
    </div>
  );
}
