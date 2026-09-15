/**
 * src/components/common/AudioWalkthrough.jsx
 * LegalEase AI — "Listen to Summary" Accessibility Feature
 *
 * Fetches the synthesized MP3 audio summary via getAudioSummary(documentId)
 * and renders a native HTML5 <audio controls> player.
 *
 * Key features:
 * - Styled "Listen to Summary" button following the navy/teal/gold design system.
 * - Loading indicator ("Preparing audio...").
 * - Clean object URL lifecycle management (URL.revokeObjectURL on unmount & refresh).
 * - No autoplay (user controls playback explicitly).
 * - Inline error reporting.
 * - Accessible text, keyboard support, and ARIA roles.
 */

import { useState, useEffect, useRef } from 'react';
import { getAudioSummary } from '../../api';
import './AudioWalkthrough.css';

export default function AudioWalkthrough({ documentId }) {
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const currentUrlRef           = useRef(null);

  // Clean up object URL on unmount or when documentId changes to prevent memory leaks
  useEffect(() => {
    return () => {
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
        currentUrlRef.current = null;
      }
    };
  }, [documentId]);

  async function handleLoadAudio() {
    if (loading) return; // Prevent duplicate requests
    if (!documentId) {
      setError('Document identifier is missing.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const blob = await getAudioSummary(documentId);
      // Revoke any previously generated object URL before creating a new one
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
      }
      const url = URL.createObjectURL(blob);
      currentUrlRef.current = url;
      setAudioUrl(url);
    } catch (err) {
      setError(err.message || 'Failed to prepare audio summary. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="audio-walkthrough"
      role="region"
      aria-label="Audio summary player"
    >
      <div className="audio-walkthrough__header">
        <div className="audio-walkthrough__info">
          <span className="audio-walkthrough__label">
            <span aria-hidden="true">🔊</span> Audio Summary
          </span>
          <span className="audio-walkthrough__sub">
            Listen to an AI-narrated summary of this legal document
          </span>
        </div>

        {/* Initial button or reload button */}
        {!audioUrl && !loading && (
          <button
            type="button"
            id="listen-to-summary-btn"
            className="audio-walkthrough__btn"
            onClick={handleLoadAudio}
            disabled={loading}
            aria-label="Listen to Summary"
          >
            <span className="audio-walkthrough__btn-icon" aria-hidden="true">▶</span>
            Listen to Summary
          </button>
        )}

        {audioUrl && !loading && (
          <button
            type="button"
            id="reload-summary-audio-btn"
            className="audio-walkthrough__reload-btn"
            onClick={handleLoadAudio}
            disabled={loading}
            aria-label="Reload Audio Summary"
            title="Reload audio summary"
          >
            <span aria-hidden="true">↻</span> Reload Audio
          </button>
        )}
      </div>

      {/* Loading state */}
      {loading && (
        <div
          className="audio-walkthrough__loading"
          role="status"
          aria-live="polite"
        >
          <div className="audio-walkthrough__spinner" aria-hidden="true" />
          <span>Preparing audio...</span>
        </div>
      )}

      {/* Audio player container with native controls */}
      {audioUrl && !loading && (
        <div className="audio-walkthrough__player-container">
          <audio
            id="summary-audio-player"
            className="audio-walkthrough__player"
            controls
            preload="metadata"
            src={audioUrl}
            aria-label="Document summary audio narration"
          >
            Your browser does not support the audio element.
          </audio>
        </div>
      )}

      {/* Inline error message */}
      {error && (
        <div
          className="audio-walkthrough__error"
          role="alert"
          aria-live="assertive"
        >
          <span className="audio-walkthrough__error-icon" aria-hidden="true">⚠️</span>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
