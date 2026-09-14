/**
 * Sidebar.jsx — Persistent left-rail navigation shell.
 *
 * Contains:
 *  - Brand mark + app name
 *  - "New Document" upload button (primary action)
 *  - Search + scrollable document list
 *  - User avatar chip + logout button (footer)
 *
 * Fetches the user's document list internally.
 * Accepts an activeDocId prop to highlight the current document.
 * Calls onDocSelect(id) when a document row is clicked.
 * Calls onUpload() to open the upload modal.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { listDocuments } from '../api';
import StatusPill from './common/StatusPill';

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short',
  });
}

function initials(name) {
  if (!name) return '?';
  return name.trim().split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
}

// Doc icon SVG
const DocIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
);

// Upload icon SVG
const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);

// Logout icon
const LogoutIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

// Hamburger icon
const HamburgerIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="3" y1="12" x2="21" y2="12"/>
    <line x1="3" y1="6" x2="21" y2="6"/>
    <line x1="3" y1="18" x2="21" y2="18"/>
  </svg>
);

// Close icon
const CloseIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

export default function Sidebar({ activeDocId, onUpload, refreshKey }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [mobileOpen, setMobileOpen] = useState(false);

  const fetchDocs = useCallback(async () => {
    try {
      const docs = await listDocuments();
      docs.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
      setDocuments(docs);
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs, refreshKey]);

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  function handleDocClick(id) {
    navigate(`/workspace/${id}`);
    setMobileOpen(false);
  }

  const filtered = search.trim()
    ? documents.filter((d) =>
        d.filename.toLowerCase().includes(search.toLowerCase())
      )
    : documents;

  const displayName = user?.business_name || user?.name || 'User';
  const displayEmail = user?.email || '';

  const sidebarContent = (
    <aside
      className={`sidebar${mobileOpen ? ' sidebar--open' : ''}`}
      aria-label="Main navigation"
    >
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo" aria-hidden="true">⚖</div>
        <div className="sidebar__app-name">
          LegalEase <em style={{ fontStyle: 'normal', color: '#8fa8ff' }}>AI</em>
          <span>Indian Business Law</span>
        </div>
      </div>

      {/* New Document button */}
      <div className="sidebar__upload-wrap">
        <button
          id="sidebar-new-doc-btn"
          className="sidebar__upload-btn"
          onClick={() => { onUpload(); setMobileOpen(false); }}
          aria-label="Upload a new document"
        >
          <UploadIcon />
          New Document
        </button>
      </div>

      {/* Section label */}
      <div className="sidebar__section-label">Documents</div>

      {/* Search */}
      <div className="sidebar__search-wrap">
        <input
          id="sidebar-search"
          className="sidebar__search"
          type="search"
          placeholder="Search documents…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search documents"
        />
      </div>

      {/* Document list */}
      <div className="sidebar__doc-list" role="list" aria-label="Your documents">
        {loading && (
          <div className="sidebar__loading">
            <div style={{ width: 18, height: 18, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.1)', borderTopColor: '#4f6ef7', animation: 'spin 0.7s linear infinite' }} />
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <p className="sidebar__empty">
            {search ? 'No documents match your search.' : 'No documents yet. Upload one to get started.'}
          </p>
        )}

        {!loading && filtered.map((doc) => (
          <button
            key={doc.id}
            id={`doc-item-${doc.id}`}
            role="listitem"
            className={`sidebar__doc-item${activeDocId === String(doc.id) ? ' sidebar__doc-item--active' : ''}`}
            onClick={() => handleDocClick(doc.id)}
            aria-label={`Open ${doc.filename}`}
            aria-current={activeDocId === String(doc.id) ? 'page' : undefined}
          >
            <div className="sidebar__doc-icon" aria-hidden="true">
              <DocIcon />
            </div>
            <div className="sidebar__doc-info">
              <span className="sidebar__doc-name" title={doc.filename}>
                {doc.filename}
              </span>
              <div className="sidebar__doc-meta">
                <span className="sidebar__doc-date">{formatDate(doc.upload_date)}</span>
                <StatusPill status={doc.status} />
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__user-avatar" aria-hidden="true">
          {initials(displayName)}
        </div>
        <div className="sidebar__user-info">
          <span className="sidebar__user-name" title={displayName}>{displayName}</span>
          <span className="sidebar__user-email" title={displayEmail}>{displayEmail}</span>
        </div>
        <button
          id="sidebar-logout-btn"
          className="sidebar__logout-btn"
          onClick={handleLogout}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogoutIcon />
        </button>
      </div>
    </aside>
  );

  return (
    <>
      {/* Mobile hamburger toggle */}
      <button
        className="sidebar__mobile-toggle"
        onClick={() => setMobileOpen((o) => !o)}
        aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        aria-expanded={mobileOpen}
      >
        {mobileOpen ? <CloseIcon /> : <HamburgerIcon />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="sidebar-overlay sidebar-overlay--visible"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {sidebarContent}
    </>
  );
}
