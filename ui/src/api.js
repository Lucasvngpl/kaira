// All API calls live in this one module (house rule: components import named
// functions, never a URL). axios behind one instance; one-liners unwrap .data.
import axios from 'axios';

// Kaira's API runs on 8300 (8000 is squatted by Django dev servers).
const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8300';

const client = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
  // Everything here is a local round trip; a poll that hangs longer than this
  // is dead and should fail catchably instead of stacking up.
  timeout: 8000,
});

export const getRoot = () => client.get('/').then((r) => r.data);

export const startSession = (patient_ref, domain) =>
  client.post('/session/start', { patient_ref, domain }).then((r) => r.data);

export const getBaselineStatus = (id) =>
  client.get(`/session/${id}/baseline-status`).then((r) => r.data);

export const getNextTask = (id) => client.get(`/session/${id}/next-task`).then((r) => r.data);

export const postAnswer = (id, task_id, result, elapsed_seconds) =>
  client.post(`/session/${id}/answer`, { task_id, result, elapsed_seconds }).then((r) => r.data);

export const getReport = (id) => client.get(`/session/${id}/report`).then((r) => r.data);

export const getLiveLoad = (id) => client.get(`/session/${id}/live-load`).then((r) => r.data);

// House error cascade: server detail if present, else the transport message.
export const errorText = (e) =>
  e.response?.data?.detail || e.response?.data?.error || e.message || 'Something went wrong';

// 409 means "wrong phase" (session ended, baseline still running) - callers
// branch on it, e.g. next-task after the cap ended the session.
export const isConflict = (e) => e.response?.status === 409;
