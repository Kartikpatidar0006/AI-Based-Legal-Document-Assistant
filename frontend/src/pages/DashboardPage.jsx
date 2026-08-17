/**
 * DashboardPage — lists the user's documents and hosts the Upload modal.
 *
 * Fetches GET /documents on mount and after each new upload.
 * Clicking a document row navigates to /documents/:id (analysis page).
 * Empty state shows a clear invitation to upload the first document.
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

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
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
          + Upload Document
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

      {!loading && !error && documents.length === 0 && (
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">📋</span>
          <h2 className="empty-state__heading">No documents yet</h2>
          <p className="empty-state__text">
            Upload your first contract or legal document to get an AI-powered
            risk assessment in under a minute.
          </p>
          <button
            id="empty-upload-btn"
            className="btn btn--primary"
            onClick={() => setShowUpload(true)}
          >
            Upload Your First Document
          </button>
        </div>
      )}

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
                  className="doc-table__row"
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

      {/* ── Upload modal ─────────────────────────────────────────────────── */}
      {showUpload && (
        <UploadDocument
          onClose={() => setShowUpload(false)}
          onComplete={handleUploadComplete}
        />
      )}
    </div>
  );
}
