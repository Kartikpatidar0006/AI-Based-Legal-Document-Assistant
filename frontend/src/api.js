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

// ── Token management & session handling ──────────────────────────────────────

/**
 * Check whether a JWT token is expired or malformed.
 * Inspects the 'exp' claim from the base64-encoded payload.
 */
export function isTokenExpired(token) {
  if (!token || typeof token !== 'string') return true;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const payload = JSON.parse(jsonPayload);
    if (!payload || !payload.exp) return false;
    // Add 5-second buffer to handle network latency
    return payload.exp * 1000 <= Date.now() + 5000;
  } catch {
    return true;
  }
}

/**
 * Safely clear stored session tokens and notify the app of session expiration.
 */
export function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user');
  window.dispatchEvent(
    new CustomEvent('legalease:session-expired', {
      detail: { message: 'Session expired. Please log in again.' },
    })
  );
}

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
    if (!token || isTokenExpired(token)) {
      clearSession();
      throw new Error('Session expired. Please log in again.');
    }
    headers['Authorization'] = `Bearer ${token}`;
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

  if (response.status === 401) {
    clearSession();
    throw new Error('Session expired. Please log in again.');
  }

  if (response.status === 403) {
    const err = await parseError(response);
    throw new Error(err.message || 'Access denied. You do not have permission to view or modify this resource.');
  }

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

/**
 * Fetch the AI-generated audio summary as an audio Blob.
 * Handles binary audio/mpeg response differently from JSON endpoints.
 * @param {string} documentId
 * @returns {Promise<Blob>}
 */
export async function getAudioSummary(documentId) {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    clearSession();
    throw new Error('Session expired. Please log in again.');
  }

  const headers = { Authorization: `Bearer ${token}` };

  const response = await fetch(`${BASE_URL}/documents/${documentId}/audio-summary`, {
    method: 'GET',
    headers,
  });

  if (response.status === 401) {
    clearSession();
    throw new Error('Session expired. Please log in again.');
  }

  if (response.status === 403) {
    const err = await parseError(response);
    throw new Error(err.message || 'Access denied. You do not have permission to listen to this document summary.');
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return response.blob();
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

/**
 * Ask a question grounded exclusively in a specific uploaded document.
 * @param {string} documentId
 * @param {string} question
 * @param {Array<{question: string, answer: string}>} chatHistory — optional recent turns for follow-ups
 * @returns {Promise<{ question: string, answer: string, filename: string, disclaimer: string }>}
 */
export async function askDocumentQuestion(documentId, question, chatHistory = []) {
  return apiFetch(`/documents/${documentId}/ask`, {
    method: 'POST',
    body: JSON.stringify({
      question,
      chat_history: chatHistory.map((h) => ({
        question: h.question,
        answer: h.answer || '',
      })),
    }),
  });
}

