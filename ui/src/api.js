// All API calls live in this one module (house rule: components import named
// functions, never a URL). axios behind one instance; one-liners unwrap .data.
import axios from 'axios';

// Relative on purpose: "/api" means "the host that served this page", so the
// clinician laptop and the patient tablet both reach the API without anyone
// baking an IP into config. Vite relays /api to port 8300 (see vite.config.js).
// The override exists for the odd case of a UI and API on different machines.
const BASE = import.meta.env.VITE_API_BASE || '/api';

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

// Signal source: which mode we're in and whether the amp is verified.
export const getStreamStatus = () => client.get('/stream/status').then((r) => r.data);
export const setStreamMode = (mode, name = null) =>
  client.post('/stream/mode', { mode, name }).then((r) => r.data);

// Every LSL broadcast visible right now (a ~3 s scan on the server).
export const getStreamList = () => client.get('/stream/list').then((r) => r.data);

// This machine's LAN address (for the patient QR) and whether a patient
// display is currently alive.
export const getNetInfo = () => client.get('/net/info').then((r) => r.data);
export const getPatientStatus = () => client.get('/patient/status').then((r) => r.data);

// The newest running session, for the patient display's auto-attach.
export const getCurrentSession = () =>
  client.get('/session/current').then((r) => r.data.session_id);

// Demo-only (400 on real hardware): ends the baseline immediately.
export const skipBaseline = (id) =>
  client.post(`/session/${id}/baseline-skip`).then((r) => r.data);

export const getNextTask = (id) => client.get(`/session/${id}/next-task`).then((r) => r.data);

// The clinician pressed Start: from here the patient screen may show the task.
export const postTaskStart = (id, task_id) =>
  client.post(`/session/${id}/task-start`, { task_id }).then((r) => r.data);

// Reuse the baseline recorded by an earlier session on this server.
export const reuseBaseline = (id) =>
  client.post(`/session/${id}/baseline-reuse`).then((r) => r.data);

export const postAnswer = (id, task_id, result, elapsed_seconds) =>
  client.post(`/session/${id}/answer`, { task_id, result, elapsed_seconds }).then((r) => r.data);

export const getReport = (id) => client.get(`/session/${id}/report`).then((r) => r.data);

export const getLiveLoad = (id) => client.get(`/session/${id}/live-load`).then((r) => r.data);

// Read-only and sample-free: safe for a second device to poll forever.
export const getPatientView = (id) =>
  client.get(`/session/${id}/patient-view`).then((r) => r.data);

// House error cascade: server detail if present, else the transport message.
export const errorText = (e) =>
  e.response?.data?.detail || e.response?.data?.error || e.message || 'Something went wrong';

// 409 means "wrong phase" (session ended, baseline still running) - callers
// branch on it, e.g. next-task after the cap ended the session.
export const isConflict = (e) => e.response?.status === 409;
