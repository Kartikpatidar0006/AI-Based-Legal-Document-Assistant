/**
 * src/api.js
 * Centralized API client for the Legal Document Assistant backend.
 *
 * All requests go to VITE_API_BASE_URL (http://localhost:8000 by default).
 * Protected calls automatically attach the stored Bearer token.
 * FastAPI error shapes are normalized into plain JS Errors so callers
 * only need to catch one error shape.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ── Token management ─────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('access_token');
}

// ── Error normalizer ─────────────────────────────────────────────────────────
// FastAPI can return:
//   { "detail": "string" }
//   { "detail": [ { "msg": "...", "loc": [...] } ] }  (validation errors)

async function parseError(response) {
  let message = `HTTP ${response.status}`;
  try {
    const data = await response.json();
    if (typeof data.detail === 'string') {
      message = data.detail;
    } else if (Array.isArray(data.detail)) {
      message = data.detail.map((e) => e.msg).join('; ');
    }
  } catch {
    // body wasn't JSON — keep the generic HTTP status message
  }
  return new Error(message);
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function apiFetch(path, options = {}, requiresAuth = true) {
  const headers = { ...options.headers };

  if (requiresAuth) {
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  // Only set Content-Type to JSON when we're sending a plain object body,
  // not when sending FormData (file uploads).
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  // 204 No Content
  if (response.status === 204) return null;

  return response.json();
}

// ── Auth endpoints ────────────────────────────────────────────────────────────

/**
 * Register a new user.
 * @returns {{ access_token, token_type, user }}
 */
export async function registerUser({ name, email, password, business_name }) {
  return apiFetch(
    '/auth/register',
    { method: 'POST', body: JSON.stringify({ name, email, password, business_name }) },
    false
  );
}

/**
 * Login with email + password.
 * @returns {{ access_token, token_type, user }}
 */
export async function loginUser({ email, password }) {
  return apiFetch(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ email, password }) },
    false
  );
}

// ── Document endpoints ────────────────────────────────────────────────────────

/**
 * Upload a document file.
 * @param {File} file
 * @param {string} [documentType]
 * @returns {{ id, filename, char_count, warnings, ... }}
 */
export async function uploadDocument(file, documentType = '') {
  const formData = new FormData();
  formData.append('file', file);
  if (documentType) formData.append('document_type', documentType);

  return apiFetch('/documents/upload', { method: 'POST', body: formData });
}

/**
 * Trigger AI analysis for an already-uploaded document.
 * This call takes 15–40 seconds (multiple Gemini calls on the backend).
 * @param {string} documentId
 * @returns {AnalysisResult}
 */
export async function analyzeDocument(documentId) {
  return apiFetch(`/documents/${documentId}/analyze`, { method: 'POST' });
}

/**
 * List all documents for the authenticated user.
 * @returns {Array<{id, filename, document_type, upload_date, status}>}
 */
export async function listDocuments() {
  return apiFetch('/documents');
}

/**
 * Get the full detail of a single document including persisted risk_flags.
 * @param {string} documentId
 */
export async function getDocument(documentId) {
  return apiFetch(`/documents/${documentId}`);
}

// ── Query endpoint ────────────────────────────────────────────────────────────

/**
 * Ask a question against the RAG knowledge base.
 * @param {string} question
 * @param {string|null} categoryFilter  — 'templates' | 'compliance_docs' | null
 * @returns {{ query, answer, sources, chunks_used }}
 */
export async function askQuery(question, categoryFilter = null) {
  return apiFetch('/query', {
    method: 'POST',
    body: JSON.stringify({ question, category_filter: categoryFilter }),
  });
}
