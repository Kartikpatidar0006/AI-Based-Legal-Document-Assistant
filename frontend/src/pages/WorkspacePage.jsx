/**
 * WorkspacePage.jsx — Unified GPT-style chat interface.
 *
 * One screen does everything:
 *  - Ask any legal question → AI answers with sources (like ChatGPT)
 *  - Upload a document directly from the chat (paperclip button)
 *  - Document uploads inline: shows progress → analysis summary card
 *  - "View Full Analysis" link opens /workspace/:id for detailed tabs
 *  - KB topic tags and quick-action chips fill the composer instantly
 *  - No separate sections, no navigation needed — everything flows in one thread
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { askQuery, uploadDocument, analyzeDocument } from '../api';

/* ─── Data ──────────────────────────────────────────────────────────────────── */

const QUICK_ACTIONS = [
  {
    id: 'summarize',
    emoji: '📄',
    label: 'Summarize a Contract',
    sub: 'Upload → get plain-language summary',
    triggerUpload: true,
    prompt: 'I want to summarize a contract. Please upload one.',
  },
  {
    id: 'risky-clauses',
    emoji: '🛡️',
    label: 'Check for Risky Clauses',
    sub: 'Find one-sided or high-risk terms',
    triggerUpload: true,
    prompt: 'Check my document for risky or one-sided clauses under Indian law.',
  },
  {
    id: 'nda',
    emoji: '✍️',
    label: 'Review an NDA',
    sub: 'Scope, confidentiality, enforceability',
    triggerUpload: true,
    prompt: 'Review my NDA for scope, confidentiality terms, and enforceability.',
  },
  {
    id: 'compliance',
    emoji: '⚖️',
    label: 'Ask About Compliance',
    sub: 'GST, MSME, Labour Law & more',
    triggerUpload: false,
    prompt: 'What are my GST and MSME compliance obligations as a small business in India?',
  },
];

const KB_TAGS = [
  { id: 'gst',     label: 'GST',                     q: 'Explain GST registration and compliance requirements for small businesses in India.' },
  { id: 'msme',    label: 'MSME & Udyam',             q: 'What are the MSME registration thresholds and benefits under the Udyam portal?' },
  { id: 'startup', label: 'Startup India',            q: 'How do I register under Startup India and what tax exemptions apply?' },
  { id: 'labour',  label: 'Labour Law',               q: 'What labour law obligations apply to a small business with fewer than 10 employees in India?' },
  { id: 'shops',   label: 'Shops & Estab. Act',       q: 'What does the Shop and Establishment Act require for a small commercial office in India?' },
  { id: 'ip',      label: 'IP & Copyright',           q: 'How do I protect my intellectual property as an Indian startup?' },
  { id: 'nda',     label: 'NDA',                      q: 'What clauses must an NDA include to be legally enforceable in India?' },
  { id: 'contract',label: 'Contracts',                q: 'Is a non-compete clause enforceable in India? What are the limits?' },
];

const ANALYSIS_STEPS = [
  'Extracting text and clauses…',
  'Summarising key provisions with AI…',
  'Checking for legal risks…',
];

/* ─── Helpers ───────────────────────────────────────────────────────────────── */
function firstName(n) { return n?.trim().split(/\s+/)[0] || null; }
function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }

/* ─── Sub-components ────────────────────────────────────────────────────────── */

/** AI avatar */
function AIAvatar() {
  return (
    <div className="ca-avatar ca-avatar--ai" aria-hidden="true">⚖</div>
  );
}

/** Welcome state — shown when chat is empty */
function WelcomeState({ name, greeting, onFill, onFileClick }) {
  return (
    <div className="ca-welcome">
      <p className="ca-welcome__eyebrow">{greeting}</p>
      <h1 className="ca-welcome__headline">
        Hi {name}, <span className="ca-welcome__sub">what can I help you with?</span>
      </h1>
      <p className="ca-welcome__tagline">
        Ask any legal question, or upload a contract to get an instant AI analysis — right here in this chat.
      </p>

      {/* Quick action cards */}
      <div className="ca-action-grid" role="list">
        {QUICK_ACTIONS.map((a) => (
          <button
            key={a.id}
            id={`qa-${a.id}`}
            type="button"
            role="listitem"
            className="ca-action-card"
            onClick={() => a.triggerUpload ? onFileClick(a.prompt) : onFill(a.prompt)}
          >
            <span className="ca-action-card__emoji" aria-hidden="true">{a.emoji}</span>
            <span className="ca-action-card__label">{a.label}</span>
            <span className="ca-action-card__sub">{a.sub}</span>
          </button>
        ))}
      </div>

      {/* KB topic tags */}
      <div className="ca-tag-row" aria-label="Topic shortcuts">
        {KB_TAGS.map((t) => (
          <button
            key={t.id}
            id={`kb-${t.id}`}
            type="button"
            className="ca-tag"
            onClick={() => onFill(t.q)}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Typing / loading indicator */
function TypingDots() {
  return (
    <div className="ca-msg ca-msg--ai" role="status" aria-label="LegalEase AI is thinking">
      <AIAvatar />
      <div className="ca-bubble ca-bubble--ai">
        <div className="ca-typing-dots" aria-hidden="true">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}

/** Document upload / analysis card (inline in chat) */
function DocCard({ msg, onView }) {
  const phaseLabel = {
    uploading:  'Uploading…',
    analyzing:  'Analysing with AI…',
    done:       'Analysis complete',
    error:      'Failed',
  }[msg.phase] || '';

  const stepIndex = msg.stepIndex ?? 0;

  return (
    <div className="ca-msg ca-msg--ai">
      <AIAvatar />
      <div className="ca-doc-card">
        {/* Header */}
        <div className="ca-doc-card__header">
          <span className="ca-doc-card__icon" aria-hidden="true">📄</span>
          <div className="ca-doc-card__info">
            <span className="ca-doc-card__name">{msg.filename}</span>
            <span className={`ca-doc-card__phase ca-doc-card__phase--${msg.phase}`}>
              {msg.phase === 'done' && <span className="ca-doc-card__check">✓ </span>}
              {phaseLabel}
            </span>
          </div>
          {(msg.phase === 'uploading' || msg.phase === 'analyzing') && (
            <div className="ca-doc-card__spinner" aria-hidden="true" />
          )}
        </div>

        {/* Analysis step list during analysis */}
        {msg.phase === 'analyzing' && (
          <div className="ca-doc-card__steps">
            {ANALYSIS_STEPS.map((s, i) => (
              <div
                key={i}
                className={
                  'ca-doc-step' +
                  (i < stepIndex ? ' ca-doc-step--done' : '') +
                  (i === stepIndex ? ' ca-doc-step--active' : '')
                }
              >
                <span className="ca-doc-step__dot" />
                <span className="ca-doc-step__label">{s}</span>
              </div>
            ))}
          </div>
        )}

        {/* Done state — CTA */}
        {msg.phase === 'done' && msg.docId && (
          <div className="ca-doc-card__footer">
            <p className="ca-doc-card__done-text">
              Your document has been analysed. View the full Summary, Clauses, and Risk Report.
            </p>
            <button
              type="button"
              className="ca-doc-card__view-btn"
              onClick={() => onView(msg.docId)}
            >
              View Full Analysis →
            </button>
          </div>
        )}

        {/* Error state */}
        {msg.phase === 'error' && (
          <div className="ca-doc-card__footer" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <p style={{ color: 'var(--color-red-dim)', fontSize: 'var(--text-sm)', margin: 0 }}>
              {msg.error || 'Something went wrong. Please try again.'}
            </p>
            {msg.error && msg.error.includes('Session expired') && (
              <a
                href="/login"
                className="btn btn--sm btn--primary"
                style={{ alignSelf: 'flex-start', textDecoration: 'none' }}
              >
                Log In Again
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** A single user or AI message */
function ChatMessage({ msg, onView }) {
  if (msg.role === 'doc') return <DocCard msg={msg} onView={onView} />;

  if (msg.role === 'user') {
    return (
      <div className="ca-msg ca-msg--user">
        <div className="ca-bubble ca-bubble--user">{msg.content}</div>
      </div>
    );
  }

  if (msg.role === 'error') {
    return (
      <div className="ca-msg ca-msg--ai">
        <AIAvatar />
        <div className="ca-bubble ca-bubble--ai ca-bubble--error">
          ⚠️ {msg.content}
        </div>
      </div>
    );
  }

  // role === 'assistant'
  const lines = (msg.content || '').split('\n').filter((l) => l.trim());
  return (
    <div className="ca-msg ca-msg--ai">
      <AIAvatar />
      <div className="ca-bubble ca-bubble--ai">
        <div className="ca-bubble__body">
          {lines.map((line, i) => <p key={i}>{line}</p>)}
        </div>

        {/* Sources */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="ca-sources">
            <span className="ca-sources__label">
              Grounded in {msg.chunks_used != null ? `${msg.chunks_used} passage${msg.chunks_used !== 1 ? 's' : ''}` : 'knowledge base'}
            </span>
            <div className="ca-sources__chips">
              {msg.sources.map((s, i) => (
                <span key={i} className="ca-source-chip">
                  📄 <span>{s.filename}</span>
                  {s.similarity_score != null && (
                    <span className="ca-source-chip__score">
                      {Math.round(s.similarity_score * 100)}%
                    </span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════════
   WorkspacePage — main export
   ═══════════════════════════════════════════════════════════════════════════════ */
export default function WorkspacePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  /* Chat state */
  const [messages, setMessages] = useState([]);
  const [input,    setInput]    = useState('');
  const [querying, setQuerying] = useState(false);

  /* Refs */
  const fileInputRef   = useRef(null);
  const textareaRef    = useRef(null);
  const messagesEndRef = useRef(null);

  /* Step cycling ref for analysis card */
  const stepTimerRef = useRef(null);

  /* Greeting */
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const name = firstName(user?.name) || user?.business_name || 'there';

  /* Auto-scroll to newest message */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, querying]);

  /* Auto-resize textarea */
  function autoResize(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 180) + 'px';
  }

  /* Fill the text input with a suggestion */
  function fillInput(text) {
    setInput(text);
    setTimeout(() => {
      const el = textareaRef.current;
      if (el) { autoResize(el); el.focus(); }
    }, 0);
  }

  /* ── Send a text question ─────────────────────────────────────────────── */
  const sendMessage = useCallback(async (overrideText) => {
    const q = (overrideText || input).trim();
    if (!q || querying) return;
    setInput('');
    setTimeout(() => autoResize(textareaRef.current), 0);

    const userMsg = { id: uid(), role: 'user', content: q };
    setMessages((prev) => [...prev, userMsg]);
    setQuerying(true);

    try {
      const res = await askQuery(q, null);
      setMessages((prev) => [
        ...prev,
        {
          id: uid(), role: 'assistant',
          content: res.answer,
          sources: res.sources || [],
          chunks_used: res.chunks_used,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: 'error', content: err.message || 'Request failed. Please try again.' },
      ]);
    } finally {
      setQuerying(false);
    }
  }, [input, querying]);

  /* ── Upload a document from the chat ─────────────────────────────────── */
  async function handleFileUpload(file, userPromptText) {
    if (!file) return;

    /* Show a user "message" describing the action */
    if (userPromptText) {
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: 'user', content: userPromptText },
      ]);
    }

    const docMsgId = uid();
    setMessages((prev) => [
      ...prev,
      { id: docMsgId, role: 'doc', filename: file.name, phase: 'uploading', docId: null, stepIndex: 0 },
    ]);

    try {
      /* Upload */
      const uploaded = await uploadDocument(file, '');

      setMessages((prev) =>
        prev.map((m) => m.id === docMsgId ? { ...m, phase: 'analyzing', docId: uploaded.id } : m)
      );

      /* Cycle step labels client-side */
      let step = 0;
      stepTimerRef.current = setInterval(() => {
        step = (step + 1) % ANALYSIS_STEPS.length;
        setMessages((prev) =>
          prev.map((m) => m.id === docMsgId ? { ...m, stepIndex: step } : m)
        );
      }, 7000);

      /* Analyse (long-running, ~15-40s) */
      await analyzeDocument(uploaded.id);

      clearInterval(stepTimerRef.current);
      setMessages((prev) =>
        prev.map((m) => m.id === docMsgId ? { ...m, phase: 'done', stepIndex: 0 } : m)
      );
    } catch (err) {
      clearInterval(stepTimerRef.current);
      setMessages((prev) =>
        prev.map((m) => m.id === docMsgId
          ? { ...m, phase: 'error', error: err.message || 'Upload failed. Please try again.' }
          : m
        )
      );
    }
  }

  /* Triggered by file input */
  function onFileInputChange(e) {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file, `📎 ${file.name}`);
      e.target.value = ''; // allow re-selecting same file
    }
  }

  /* Triggered by quick-action chips that need a doc */
  function triggerFilePickerWithPrompt(promptText) {
    /* Show user "message" to give context, then open file picker */
    setMessages((prev) => [...prev, { id: uid(), role: 'user', content: promptText }]);
    setTimeout(() => fileInputRef.current?.click(), 100);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="ca-page">

      {/* ── Hidden file input ─────────────────────────────────────────────── */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.jpg,.jpeg,.png,.tiff,.bmp"
        style={{ display: 'none' }}
        onChange={onFileInputChange}
        aria-hidden="true"
      />

      {/* ── Chat messages area ────────────────────────────────────────────── */}
      <div className="ca-messages" role="log" aria-live="polite" aria-label="Conversation">

        {isEmpty ? (
          <WelcomeState
            name={name}
            greeting={greeting}
            onFill={fillInput}
            onFileClick={triggerFilePickerWithPrompt}
          />
        ) : (
          <div className="ca-thread">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                msg={msg}
                onView={(docId) => navigate(`/workspace/${docId}`)}
              />
            ))}
            {querying && <TypingDots />}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Compact KB tags row (visible once chat has started) ───────────── */}
      {!isEmpty && (
        <div className="ca-tags-bar" aria-label="Topic shortcuts">
          {KB_TAGS.map((t) => (
            <button
              key={t.id}
              type="button"
              className="ca-tag"
              onClick={() => fillInput(t.q)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {/* ── Composer ─────────────────────────────────────────────────────── */}
      <div className="ca-composer-wrap">
        <div className="ca-composer">
          {/* Attach button */}
          <button
            id="chat-attach-btn"
            type="button"
            className="ca-attach-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Upload a document"
            aria-label="Upload a document"
          >
            {/* Paperclip icon */}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
            </svg>
          </button>

          {/* Text input */}
          <label htmlFor="ca-input" className="sr-only">Ask a legal question</label>
          <textarea
            id="ca-input"
            ref={textareaRef}
            className="ca-textarea"
            value={input}
            placeholder="Ask a legal question, or click 📎 to upload a document…"
            rows={1}
            disabled={querying}
            onChange={(e) => { setInput(e.target.value); autoResize(e.target); }}
            onKeyDown={handleKeyDown}
          />

          {/* Send button */}
          <button
            id="ca-send-btn"
            type="button"
            className="ca-send-btn"
            disabled={!input.trim() || querying}
            onClick={() => sendMessage()}
            aria-label="Send message"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>

        <p className="ca-disclaimer">
          LegalEase AI may make mistakes. Always consult a qualified lawyer for specific legal advice.
        </p>
      </div>

    </div>
  );
}
