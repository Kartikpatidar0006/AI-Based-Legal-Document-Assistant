/**
 * AudioWalkthrough — Voice-based audio summary player.
 *
 * Fetches the synthesized MP3 audio summary via getAudioSummary(documentId)
 * and renders an HTML5 <audio controls> player.
 *
 * Key features:
 * - On-brand "Listen to Summary" button (navy/teal) with speaker icon.
 * - Non-blocking loading state ("Preparing audio walkthrough…").
 * - Clean object URL lifecycle management (URL.revokeObjectURL on unmount).
 * - No autoplay (user explicitly controls playback).
 * - Clear inline error reporting.
 */

import { useState, useEffect, useRef } from 'react';
import { getAudioSummary } from '../../api';

export default function AudioWalkthrough({ documentId }) {
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const currentUrlRef           = useRef(null);

  // Clean up object URL on unmount or documentId change to prevent memory leaks
  useEffect(() => {
    return () => {
      if (currentUrlRef.current) {
        URL.revokeObjectURL(currentUrlRef.current);
        currentUrlRef.current = null;
      }
    };
  }, [documentId]);

  async function handleLoadAudio() {
    if (loading) return;
    setLoading(true);
    setError('');

    try {
      const blob = await getAudioSummary(documentId);
      // Revoke any previous URL
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
    <div className="audio-walkthrough" aria-label="Audio summary walkthrough">
      {!audioUrl && !loading && (
        <div className="audio-walkthrough__cta">
          <button
            type="button"
            className="btn btn--outline-teal audio-walkthrough__btn"
            onClick={handleLoadAudio}
            aria-label="Listen to summary audio"
          >
            <span className="audio-walkthrough__icon" aria-hidden="true">🔊</span>
            <span className="audio-walkthrough__btn-text">Listen to Summary</span>
          </button>
          <span className="audio-walkthrough__hint">
            AI-narrated voice overview of this contract
          </span>
        </div>
      )}

      {loading && (
        <div className="audio-walkthrough__loading" role="status">
          <span className="audio-walkthrough__spinner" aria-hidden="true" />
          <span>Preparing audio walkthrough…</span>
        </div>
      )}

      {audioUrl && !loading && (
        <div className="audio-walkthrough__player-wrap">
          <div className="audio-walkthrough__player-header">
            <div className="audio-walkthrough__status">
              <span className="audio-walkthrough__badge-dot" aria-hidden="true" />
              <span className="audio-walkthrough__badge-text">Audio Summary</span>
            </div>
            <button
              type="button"
              className="audio-walkthrough__reload-btn"
              onClick={handleLoadAudio}
              title="Refresh audio"
              aria-label="Regenerate audio"
            >
              ↻ Reload
            </button>
          </div>
          <audio
            className="audio-walkthrough__player"
            controls
            preload="metadata"
            src={audioUrl}
          >
            Your browser does not support the audio element.
          </audio>
        </div>
      )}

      {error && (
        <div className="audio-walkthrough__error form-error" role="alert">
          <span className="audio-walkthrough__error-icon" aria-hidden="true">⚠️</span>
          <span>{error}</span>
          <button
            type="button"
            className="audio-walkthrough__retry-btn"
            onClick={handleLoadAudio}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
