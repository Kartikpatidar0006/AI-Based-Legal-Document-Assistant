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
        <>
          <div className="audio-walkthrough__info">
            <span className="audio-walkthrough__label">Voice Walkthrough</span>
            <span className="audio-walkthrough__sub">AI-narrated overview of this contract</span>
          </div>
          <button
            type="button"
            className="audio-walkthrough__btn"
            onClick={handleLoadAudio}
            aria-label="Listen to summary audio"
          >
            🔊 Listen
          </button>
        </>
      )}

      {loading && (
        <div role="status" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>
          <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid var(--color-border)', borderTopColor: 'var(--color-primary)', animation: 'spin 0.7s linear infinite' }} />
          Preparing audio walkthrough…
        </div>
      )}

      {audioUrl && !loading && (
        <>
          <div className="audio-walkthrough__info">
            <span className="audio-walkthrough__label">Audio Summary</span>
            <button
              type="button"
              className="audio-walkthrough__btn"
              onClick={handleLoadAudio}
              title="Refresh audio"
              style={{ padding: '4px 10px', fontSize: 'var(--text-xs)' }}
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
        </>
      )}

      {error && (
        <div className="audio-walkthrough__error" role="alert">{error}</div>
      )}
    </div>
  );
}
