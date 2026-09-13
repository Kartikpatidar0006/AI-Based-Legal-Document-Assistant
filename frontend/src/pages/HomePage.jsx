/**
 * HomePage.jsx — Personalized landing screen for authenticated users.
 *
 * Sections (top → bottom, decreasing visual weight):
 *  1. Personalized greeting (serif headline)
 *  2. Central action composer: text input (→ /query) + Upload button (→ modal)
 *  3. Quick-action chips: product-specific shortcuts
 *  4. Knowledge-base category tags: navigate to /query with a pre-filled question
 *  5. Recent documents preview (2–3 most recent; hidden when user has none)
 *
 * Routing: this lives at "/" — DashboardPage has been moved to "/documents".
 * All API calls, auth, and routing reuse existing infrastructure.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { listDocuments } from '../api';
import StatusPill from '../components/common/StatusPill';
import UploadDocument from '../components/UploadDocument';

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

/** "Priya Sharma" → "Priya" */
function firstName(fullName) {
  if (!fullName) return null;
  return fullName.trim().split(/\s+/)[0];
}

/* ── Quick-action chip definitions ───────────────────────────────────────── */

const QUICK_ACTIONS = [
  {
    id: 'summarize',
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    ),
    label: 'Summarize a Contract',
    action: (_navigate, setShowUpload, setUploadHint) => {
      setUploadHint('Upload a contract to get a plain-language summary of its key terms and obligations.');
      setShowUpload(true);
    },
  },
  {
    id: 'risky-clauses',
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
    ),
    label: 'Check for Risky Clauses',
    action: (_navigate, setShowUpload, setUploadHint) => {
      setUploadHint('Upload a document to identify high-risk or one-sided clauses under Indian law.');
      setShowUpload(true);
    },
  },
  {
    id: 'compliance',
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
    ),
    label: 'Ask About Compliance (GST / MSME)',
    action: (navigate) => {
      navigate('/query', {
        state: {
          prefillQuestion: 'What are my GST and MSME compliance obligations as a small business?',
          category: 'compliance_docs',
        },
      });
    },
  },
  {
    id: 'nda',
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      </svg>
    ),
    label: 'Review an NDA',
    action: (_navigate, setShowUpload, setUploadHint) => {
      setUploadHint('Upload your NDA to check its scope, confidentiality terms, and enforceability.');
      setShowUpload(true);
    },
  },
];

/* ── Knowledge-base category tags ────────────────────────────────────────── */

const KB_TAGS = [
  { id: 'gst',     label: 'GST',                      question: 'Explain GST registration and compliance requirements for small businesses in India.' },
  { id: 'msme',    label: 'MSME & Udyam',              question: 'What are the MSME registration thresholds and benefits under the Udyam portal?' },
  { id: 'startup', label: 'Startup India',             question: 'How do I register under Startup India and what tax exemptions apply?' },
  { id: 'labour',  label: 'Labour Law',                question: 'What labour law obligations apply to a small business with fewer than 10 employees in India?' },
  { id: 'shops',   label: 'Shop & Establishment Act',  question: 'What does the Shop and Establishment Act require for a small commercial office in India?' },
];

/* ══════════════════════════════════════════════════════════════════════════
   HomePage
   ══════════════════════════════════════════════════════════════════════════ */

export default function HomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  /* Composer */
  const [queryText, setQueryText] = useState('');
  const composerRef = useRef(null);

  /* Upload modal */
  const [showUpload, setShowUpload] = useState(false);
  const [uploadHint, setUploadHint] = useState('');

  /* Recent documents */
  const [recentDocs, setRecentDocs] = useState([]);
  const [docsLoaded, setDocsLoaded] = useState(false);

  const fetchRecent = useCallback(async () => {
    try {
      const docs = await listDocuments();
      docs.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
      setRecentDocs(docs.slice(0, 3));
    } catch {
      /* Non-critical: silently skip section on error */
    } finally {
      setDocsLoaded(true);
    }
  }, []);

  useEffect(() => { fetchRecent(); }, [fetchRecent]);

  /* ── Composer: Enter submits → /query ──────────────────────────────── */
  function handleComposerSubmit(e) {
    e.preventDefault();
    const q = queryText.trim();
    if (!q) return;
    navigate('/query', { state: { prefillQuestion: q } });
  }

  function handleComposerKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleComposerSubmit(e);
    }
  }

  /* ── Upload complete → analysis page ────────────────────────────────── */
  function handleUploadComplete(documentId) {
    setShowUpload(false);
    navigate(`/documents/${documentId}`);
  }

  /* ── Quick-action chip ───────────────────────────────────────────────── */
  function handleQuickAction(chip) {
    chip.action(navigate, setShowUpload, setUploadHint);
  }

  /* ── KB tag → /query pre-filled ─────────────────────────────────────── */
  function handleKbTag(tag) {
    navigate('/query', { state: { prefillQuestion: tag.question } });
  }

  /* ── Greeting copy ───────────────────────────────────────────────────── */
  const name = firstName(user?.name);
  const greetingName = name || user?.business_name || 'there';
  const hour = new Date().getHours();
  const timeGreeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  return (
    <div className="home-page page">

      {/* ══ 1. GREETING ═══════════════════════════════════════════════════ */}
      <section className="home-greeting" aria-label="Welcome">
        <p className="home-greeting__eyebrow label-caps">{timeGreeting}</p>
        <h1 className="home-greeting__headline">
          Hi {greetingName},{' '}
          <span className="home-greeting__headline-sub">let's review your next document.</span>
        </h1>
        <p className="home-greeting__tagline">
          Upload a contract, ask a compliance question, or explore the knowledge base below.
        </p>
      </section>

      {/* ══ 2. CENTRAL ACTION COMPOSER ════════════════════════════════════ */}
      <section className="home-composer-wrap" aria-label="Main actions">
        <form
          className="home-composer"
          onSubmit={handleComposerSubmit}
          role="search"
          aria-label="Ask a legal question"
        >
          <label htmlFor="home-query-input" className="sr-only">Ask a legal question</label>
          <input
            id="home-query-input"
            ref={composerRef}
            className="home-composer__input"
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Ask a legal question…"
            autoComplete="off"
            spellCheck="false"
          />

          {/* Vertical separator — clearly separates the two distinct actions */}
          <div className="home-composer__divider" aria-hidden="true" />

          {/* Upload — always-visible, clearly labeled, opens modal */}
          <button
            id="home-upload-btn"
            type="button"
            className="home-composer__upload-btn"
            onClick={() => { setUploadHint(''); setShowUpload(true); }}
            aria-label="Upload a document for analysis"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
                 className="home-composer__upload-icon">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span>Upload Document</span>
          </button>

          {/* Ask — submits text query */}
          <button
            id="home-ask-btn"
            type="submit"
            className="home-composer__ask-btn"
            disabled={!queryText.trim()}
            aria-label="Submit question"
          >
            Ask
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                 style={{ width: '13px', height: '13px', flexShrink: 0 }}>
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </button>
        </form>

        <p className="home-composer__hint">
          Press <kbd>Enter</kbd> to submit your question
          &nbsp;·&nbsp;
          use <strong>Upload Document</strong> to analyse a contract or agreement
        </p>
      </section>

      {/* ══ 3. QUICK-ACTION CHIPS ══════════════════════════════════════════ */}
      <section className="home-chips-section" aria-label="Quick actions">
        <p className="home-section-label label-caps">Quick actions</p>
        <ul className="home-chips" role="list">
          {QUICK_ACTIONS.map((chip) => (
            <li key={chip.id}>
              <button
                id={`quick-action-${chip.id}`}
                type="button"
                className="home-chip"
                onClick={() => handleQuickAction(chip)}
              >
                <span className="home-chip__icon" aria-hidden="true">{chip.icon}</span>
                <span className="home-chip__label">{chip.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* ══ 4. KNOWLEDGE-BASE CATEGORY TAGS ═══════════════════════════════ */}
      <section className="home-tags-section" aria-label="Knowledge base categories">
        <p className="home-section-label label-caps">Explore knowledge base</p>
        <ul className="home-tags" role="list">
          {KB_TAGS.map((tag) => (
            <li key={tag.id}>
              <button
                id={`kb-tag-${tag.id}`}
                type="button"
                className="home-tag"
                onClick={() => handleKbTag(tag)}
              >
                {tag.label}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* ══ 5. RECENT DOCUMENTS (only if user has ≥1 document) ════════════ */}
      {docsLoaded && recentDocs.length > 0 && (
        <section className="home-recent" aria-label="Recent documents">
          <div className="home-recent__header">
            <p className="home-section-label label-caps" style={{ marginBottom: 0 }}>Recent documents</p>
            <a
              href="/documents"
              className="home-recent__viewall"
              onClick={(e) => { e.preventDefault(); navigate('/documents'); }}
            >
              View all →
            </a>
          </div>
          <ul className="home-recent-list" role="list">
            {recentDocs.map((doc) => (
              <li key={doc.id}>
                <button
                  type="button"
                  className="home-recent-item"
                  onClick={() => navigate(`/documents/${doc.id}`)}
                  aria-label={`Open ${doc.filename}`}
                >
                  <span className="home-recent-item__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                  </span>
                  <span className="home-recent-item__body">
                    <span className="home-recent-item__name">{doc.filename}</span>
                    <span className="home-recent-item__meta">{formatDate(doc.upload_date)}</span>
                  </span>
                  <span className="home-recent-item__status">
                    <StatusPill status={doc.status} />
                  </span>
                  <span className="home-recent-item__arrow" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ══ Upload modal ══════════════════════════════════════════════════ */}
      {showUpload && (
        <UploadDocument
          onClose={() => { setShowUpload(false); setUploadHint(''); }}
          onComplete={handleUploadComplete}
          hint={uploadHint}
        />
      )}
    </div>
  );
}
