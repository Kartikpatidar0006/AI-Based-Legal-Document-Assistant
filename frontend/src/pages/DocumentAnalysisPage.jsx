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

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDocument, analyzeDocument } from '../api';
import RiskBadge from '../components/common/RiskBadge';
import SourceChip from '../components/common/SourceChip';
import LoadingSpinner from '../components/common/LoadingSpinner';

const TABS = ['Summary', 'Clauses', 'Risk Analysis'];

// ── Sub-components ───────────────────────────────────────────────────────────

function SummarySection({ summaryResult }) {
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
          <span className="doc-header__icon" aria-hidden="true">📄</span>
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
            {activeTab === 'Summary'      && <SummarySection summaryResult={doc?.summary_result} />}
            {activeTab === 'Clauses'      && <ClausesSection clauseResult={doc?.clause_result} />}
            {activeTab === 'Risk Analysis' && <RiskSection   riskResult={doc?.risk_result} />}
          </div>
        </>
      )}
    </div>
  );
}
