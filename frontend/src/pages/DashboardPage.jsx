/**
 * DashboardPage — lists the user's documents and hosts the Upload modal.
 *
 * Fetches GET /documents on mount and after each new upload.
 * Clicking a document row navigates to /documents/:id (analysis page).
 *
 * Empty state: replaced the dashed-box-with-icon pattern with a working
 * product preview — three-step connected flow + a greyed-out example
 * analysis card. All API calls, routing, and state logic are unchanged.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDocuments } from '../api';
import { useAuth } from '../context/AuthContext';
import UploadDocument from '../components/UploadDocument';
import StatusPill from '../components/common/StatusPill';
import LoadingSpinner from '../components/common/LoadingSpinner';

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

export default function DashboardPage() {
  const { user }   = useAuth();
  const navigate   = useNavigate();

  const [documents, setDocuments]   = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [showUpload, setShowUpload] = useState(false);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const docs = await listDocuments();
      // Sort newest first
      docs.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
      setDocuments(docs);
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  function handleUploadComplete(documentId) {
    setShowUpload(false);
    navigate(`/documents/${documentId}`);
  }

  return (
    <div className="page">
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {user?.business_name ? `${user.business_name}'s Documents` : 'My Documents'}
          </h1>
          <p className="page-subtitle">
            Upload a contract, NDA, or agreement to get an instant AI risk analysis.
          </p>
        </div>
        <button
          id="open-upload-btn"
          className="btn btn--primary"
          onClick={() => setShowUpload(true)}
        >
          ↑ Upload Document
        </button>
      </div>

      {/* ── Document list ─────────────────────────────────────────────────── */}
      {loading && (
        <div className="page-loading">
          <LoadingSpinner label="Loading documents…" />
        </div>
      )}

      {!loading && error && (
        <div className="page-error" role="alert">
          {error}
          <button className="btn btn--ghost btn--sm" onClick={fetchDocuments} style={{ marginLeft: '1rem' }}>
            Retry
          </button>
        </div>
      )}

      {/* ── Empty state — onboarding flow + example preview ─────────────── */}
      {!loading && !error && documents.length === 0 && (
        <div className="dash-onboarding">

          {/* Three-step connected flow */}
          <div className="dash-steps" aria-label="How it works">
            {/* Step 1 */}
            <div className="dash-step">
              <div className="dash-step__number" aria-hidden="true">1</div>
              <div className="dash-step__body">
                <div className="dash-step__title">Upload</div>
                <p className="dash-step__desc">
                  Drop your PDF or Word document — contract, NDA, or any agreement.
                </p>
              </div>
            </div>

            {/* Connector line — the single deliberate animation moment */}
            <div className="dash-step-connector" aria-hidden="true" />

            {/* Step 2 */}
            <div className="dash-step">
              <div className="dash-step__number" aria-hidden="true">2</div>
              <div className="dash-step__body">
                <div className="dash-step__title">Analyse</div>
                <p className="dash-step__desc">
                  AI extracts every clause and scores it for legal risk under Indian law.
                </p>
              </div>
            </div>

            {/* Connector line */}
            <div className="dash-step-connector" aria-hidden="true" />

            {/* Step 3 */}
            <div className="dash-step">
              <div className="dash-step__number" aria-hidden="true">3</div>
              <div className="dash-step__body">
                <div className="dash-step__title">Review</div>
                <p className="dash-step__desc">
                  See flagged clauses, risk ratings, and plain-language explanations before you sign.
                </p>
              </div>
            </div>
          </div>

          {/* Example output preview — static, labeled, teaches the user what they'll get */}
          <div className="dash-example" aria-hidden="true">
            <div className="dash-example__label">
              <span className="dash-example__label-dot" />
              <span className="dash-example__label-text">Example output — what you'll see after analysis</span>
            </div>
            <div className="dash-example__doc-header">
              <span className="dash-example__doc-name">Vendor Services Agreement.pdf</span>
              <StatusPill status="analyzed" />
            </div>
            <div className="dash-example__risk-banner">
              <span className="dash-example__risk-score">72</span>
              <div>
                <div className="dash-example__risk-label">Overall Risk</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--color-red-dim)', fontWeight: 600 }}>High</div>
              </div>
              <span className="dash-example__risk-count">6 issues flagged</span>
            </div>
            <div className="dash-example__rows">
              <div className="dash-example__row">
                <span className="dash-example__clause">Non-Compete Clause</span>
                <span className="dash-example__clause-meta">3 yrs · All of India</span>
                <span className="dash-example__risk-pill dash-example__risk-pill--high">High</span>
              </div>
              <div className="dash-example__row">
                <span className="dash-example__clause">Payment Terms</span>
                <span className="dash-example__clause-meta">Net 90 days</span>
                <span className="dash-example__risk-pill dash-example__risk-pill--medium">Medium</span>
              </div>
              <div className="dash-example__row">
                <span className="dash-example__clause">Liability Cap</span>
                <span className="dash-example__clause-meta">₹50,000 ceiling</span>
                <span className="dash-example__risk-pill dash-example__risk-pill--high">High</span>
              </div>
              <div className="dash-example__row">
                <span className="dash-example__clause">IP Assignment</span>
                <span className="dash-example__clause-meta">Broad, perpetual</span>
                <span className="dash-example__risk-pill dash-example__risk-pill--medium">Medium</span>
              </div>
            </div>
          </div>

        </div>
      )}

      {/* ── Document table (non-empty state) — unchanged ─────────────────── */}
      {!loading && !error && documents.length > 0 && (
        <div className="doc-table-wrap">
          <table className="doc-table" aria-label="Your documents">
            <thead>
              <tr>
                <th className="doc-table__th">Filename</th>
                <th className="doc-table__th">Type</th>
                <th className="doc-table__th">Uploaded</th>
                <th className="doc-table__th">Status</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  className={`doc-table__row${doc.status === 'analyzed' ? ' doc-table__row--analyzed' : ''}`}
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/documents/${doc.id}`)}
                  aria-label={`Open ${doc.filename}`}
                >
                  <td className="doc-table__td doc-table__td--filename">
                    <span className="doc-icon" aria-hidden="true">📄</span>
                    {doc.filename}
                  </td>
                  <td className="doc-table__td doc-table__td--muted">
                    {doc.document_type || '—'}
                  </td>
                  <td className="doc-table__td doc-table__td--muted">
                    {formatDate(doc.upload_date)}
                  </td>
                  <td className="doc-table__td">
                    <StatusPill status={doc.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Upload modal — unchanged ────────────────────────────────────── */}
      {showUpload && (
        <UploadDocument
          onClose={() => setShowUpload(false)}
          onComplete={handleUploadComplete}
        />
      )}
    </div>
  );
}
