/**
 * UploadDocument — modal overlay for uploading and analysing a document.
 *
 * Flow:
 *   1. User selects/drops a file and optionally picks document_type.
 *   2. On "Upload & Analyse" click:
 *      a. POST /documents/upload   — fast, returns document ID
 *      b. POST /documents/{id}/analyse — slow (15-40 s, multiple Gemini calls)
 *         During (b) a 3-step progress indicator cycles client-side every ~8 s
 *         to set user expectations even though the backend is a single blocking call.
 *   3. On completion, call onComplete(documentId) which navigates to the analysis page.
 *
 * Props:
 *   onClose      — close the modal without uploading
 *   onComplete   — called with the new documentId when analysis finishes
 */

import { useState, useRef, useEffect } from 'react';
import { uploadDocument, analyzeDocument } from '../api';
import LoadingSpinner from './common/LoadingSpinner';

const DOCUMENT_TYPES = [
  'Employment Contract',
  'NDA',
  'Rental Agreement',
  'Service Agreement',
  'Partnership Deed',
  'Vendor Contract',
  'Loan Agreement',
  'Other',
];

// The 3 staged messages shown during the long analysis call (purely client-side
// cosmetic — the backend runs all three steps atomically).
const ANALYSIS_STEPS = [
  'Extracting text and clauses from your document…',
  'Summarising key provisions with AI…',
  'Checking for legal risks against our knowledge base…',
];

export default function UploadDocument({ onClose, onComplete }) {
  const [file, setFile]             = useState(null);
  const [docType, setDocType]       = useState('');
  const [dragOver, setDragOver]     = useState(false);

  const [phase, setPhase]           = useState('idle'); // idle | uploading | analyzing | done
  const [stepIndex, setStepIndex]   = useState(0);
  const [error, setError]           = useState('');

  const fileInputRef = useRef(null);
  const stepTimerRef = useRef(null);

  // Cycle through the 3 analysis step messages while the long API call runs
  useEffect(() => {
    if (phase === 'analyzing') {
      stepTimerRef.current = setInterval(() => {
        setStepIndex((i) => (i + 1) % ANALYSIS_STEPS.length);
      }, 8000);
    }
    return () => clearInterval(stepTimerRef.current);
  }, [phase]);

  // ── File selection ──────────────────────────────────────────────────────────
  function handleFileChange(e) {
    const selected = e.target.files?.[0];
    if (selected) { setFile(selected); setError(''); }
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) { setFile(dropped); setError(''); }
  }

  // ── Submit ──────────────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    if (!file) { setError('Please select a file to upload.'); return; }

    setError('');
    try {
      // Step 1 — upload
      setPhase('uploading');
      const uploadResult = await uploadDocument(file, docType);

      // Step 2 — analyse (long-running, ~15-40 s)
      setPhase('analyzing');
      setStepIndex(0);
      await analyzeDocument(uploadResult.id);

      setPhase('done');
      clearInterval(stepTimerRef.current);
      onComplete(uploadResult.id);
    } catch (err) {
      setPhase('idle');
      setError(err.message || 'Something went wrong. Please try again.');
    }
  }

  const isLoading = phase === 'uploading' || phase === 'analyzing';

  return (
    /* Modal backdrop */
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
      onClick={(e) => { if (!isLoading && e.target === e.currentTarget) onClose(); }}
    >
      <div className="modal-panel">
        <div className="modal-header">
          <h2 id="upload-modal-title" className="modal-title">Upload a Document</h2>
          {!isLoading && (
            <button
              id="upload-modal-close"
              className="modal-close"
              onClick={onClose}
              aria-label="Close"
            >
              ✕
            </button>
          )}
        </div>

        {/* ── Progress states ─────────────────────────────────────────────── */}
        {phase === 'uploading' && (
          <div className="upload-progress">
            <LoadingSpinner label="Uploading your document…" />
          </div>
        )}

        {phase === 'analyzing' && (
          <div className="upload-progress">
            <LoadingSpinner label="" />
            <p className="upload-progress__heading">Analysing your document</p>
            <p className="upload-progress__subtext">This can take up to 30 seconds</p>
            <div className="upload-progress__step">
              {ANALYSIS_STEPS[stepIndex]}
            </div>
            <div className="upload-progress__steps-list">
              {ANALYSIS_STEPS.map((s, i) => (
                <div
                  key={i}
                  className={
                    'upload-step' +
                    (i < stepIndex  ? ' upload-step--done' : '') +
                    (i === stepIndex ? ' upload-step--active' : '')
                  }
                >
                  <span className="upload-step__dot" />
                  <span className="upload-step__label">{s}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Upload form (only shown when idle) ─────────────────────────── */}
        {phase === 'idle' && (
          <form id="upload-form" className="upload-form" onSubmit={handleSubmit}>
            {error && <div className="form-error" role="alert">{error}</div>}

            {/* Drop zone */}
            <div
              id="upload-dropzone"
              className={'dropzone' + (dragOver ? ' dropzone--over' : '') + (file ? ' dropzone--has-file' : '')}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                id="file-input"
                type="file"
                accept=".pdf,.docx,.jpg,.jpeg,.png,.tiff,.bmp"
                className="dropzone__input"
                onChange={handleFileChange}
              />
              {file ? (
                <>
                  <span className="dropzone__file-icon">📄</span>
                  <p className="dropzone__filename">{file.name}</p>
                  <p className="dropzone__hint">Click to change file</p>
                </>
              ) : (
                <>
                  <span className="dropzone__icon" aria-hidden="true">⬆</span>
                  <p className="dropzone__prompt">Drop your file here or <span className="dropzone__browse">browse</span></p>
                  <p className="dropzone__hint">PDF, DOCX, JPG, PNG, TIFF, BMP</p>
                </>
              )}
            </div>

            {/* Document type */}
            <div className="form-group">
              <label className="form-label" htmlFor="doc-type-select">
                Document type <span className="form-label--optional">(optional)</span>
              </label>
              <select
                id="doc-type-select"
                className="form-input form-select"
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
              >
                <option value="">— Select type —</option>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            <div className="upload-form__actions">
              <button
                type="button"
                id="upload-cancel-btn"
                className="btn btn--ghost"
                onClick={onClose}
              >
                Cancel
              </button>
              <button
                id="upload-submit-btn"
                type="submit"
                className="btn btn--primary"
                disabled={!file}
              >
                Upload &amp; Analyse
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
