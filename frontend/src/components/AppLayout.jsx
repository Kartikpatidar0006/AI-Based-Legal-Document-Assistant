/**
 * AppLayout — Unified workspace shell.
 *
 * Renders the persistent Sidebar + main content area side by side.
 * Hosts the upload modal state so Sidebar's "New Document" button and
 * WorkspacePage's quick-action chips can both trigger it.
 *
 * After upload completes, navigates to /workspace/:id.
 */

import { useState, useCallback } from 'react';
import { Outlet, useNavigate, useParams } from 'react-router-dom';
import Sidebar from './Sidebar';
import UploadDocument from './UploadDocument';

export default function AppLayout() {
  const navigate   = useNavigate();
  const { id }     = useParams();

  // Upload modal state
  const [showUpload, setShowUpload] = useState(false);
  const [uploadHint, setUploadHint] = useState('');
  // Incrementing key tells Sidebar to re-fetch the doc list after upload
  const [refreshKey, setRefreshKey] = useState(0);

  const openUpload = useCallback((hint = '') => {
    setUploadHint(hint);
    setShowUpload(true);
  }, []);

  function handleUploadComplete(documentId) {
    setShowUpload(false);
    setUploadHint('');
    setRefreshKey((k) => k + 1);
    navigate(`/workspace/${documentId}`);
  }

  return (
    <div className="app-layout">
      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <Sidebar
        activeDocId={id}
        onUpload={openUpload}
        refreshKey={refreshKey}
      />

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="app-main">
        {/* Pass openUpload and hint setters down via Outlet context */}
        <Outlet context={{ openUpload, setUploadHint }} />
      </div>

      {/* ── Upload modal (global, hosted here) ───────────────────────────── */}
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
