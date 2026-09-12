// New-assessment form: patient reference + domain, then hand off to baseline.
// Also home of the signal-source switch: Test (dummy stream or generator)
// vs Live (only the real EE511 amplifier counts, verified before anything
// can start).
import { useState } from 'react';
import { FiArrowUpRight } from 'react-icons/fi';
import { startSession, getStreamStatus, setStreamMode, errorText } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import '../styles/session.css';

// What to check, in the order things actually go wrong on the day.
const LIVE_CHECKLIST = [
  'eego software: Network operations, enable LSL, streaming started',
  'Both machines on the same hotspot or network',
  'Windows firewall on the eego machine: allow the eego app',
  'Isolating wifi (eduroam/guest): lsl_api.cfg with KnownPeers = {host ip}',
];

export default function StartScreen({ info, onStarted }) {
  const [patientRef, setPatientRef] = useState('');
  const [domain, setDomain] = useState('Visuospatial');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState(null); // /stream/status, polled

  usePoll(
    async () => {
      try {
        setSource(await getStreamStatus());
      } catch {
        // API not up yet; the reachability banner covers that case.
      }
    },
    2000,
    true
  );

  const pickMode = async (mode) => {
    if (source?.mode === mode) return;
    setSource((s) => ({ ...(s || {}), mode, connected: false, detail: 'connecting...' }));
    try {
      setSource(await setStreamMode(mode));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const liveBlocked = source?.mode === 'live' && !source?.connected;

  // Until GET / answers, offer the one domain we know is populated rather
  // than an empty select.
  const domains = info ? Object.entries(info.domains) : [['Visuospatial', true]];

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await startSession(patientRef.trim(), domain);
      onStarted({
        id: res.session_id,
        baselineSeconds: res.baseline_seconds,
        patientRef: patientRef.trim(),
        domain,
      });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <div className="sn-start kr-reveal">
      <header className="kr-header">
        <h1>New assessment</h1>
        <p>Fit the cap, seat the patient, and start with a short resting baseline.</p>
      </header>

      <form className="kr-card sn-start__card" onSubmit={submit}>
        <div className="kr-field">
          <label htmlFor="patient-ref">Patient reference</label>
          <input
            id="patient-ref"
            value={patientRef}
            onChange={(e) => setPatientRef(e.target.value)}
            placeholder="PT-0416"
            required
            autoFocus
          />
        </div>

        <div className="kr-field">
          <label htmlFor="domain">Domain</label>
          <select id="domain" value={domain} onChange={(e) => setDomain(e.target.value)}>
            {domains.map(([name, populated]) => (
              <option key={name} value={name} disabled={!populated}>
                {populated ? name : `${name} (not yet populated)`}
              </option>
            ))}
          </select>
        </div>

        <div className="kr-field">
          <label>Signal source</label>
          <div className="sn-seg" role="radiogroup" aria-label="Signal source">
            <button
              type="button"
              className={`sn-seg__opt${source?.mode !== 'live' ? ' sn-seg__opt--on' : ''}`}
              onClick={() => pickMode('test')}
            >
              Test signal
            </button>
            <button
              type="button"
              className={`sn-seg__opt${source?.mode === 'live' ? ' sn-seg__opt--on' : ''}`}
              onClick={() => pickMode('live')}
            >
              Live amplifier
            </button>
          </div>
          {source?.mode === 'live' && source?.connected && (
            <p className="kr-hint">
              Amplifier verified: {source.stream} &middot; {source.fs} Hz &middot; {source.channels} channels
            </p>
          )}
          {source?.mode !== 'live' && source?.connected && (
            <p className="kr-hint">Using {source.detail}. Nothing here is a real patient.</p>
          )}
          {liveBlocked && (
            <div className="sn-lsl" role="status">
              <p className="sn-lsl__head">Looking for the amplifier&hellip; retrying every few seconds.</p>
              {source?.detail && source.detail !== 'connecting...' && (
                <p className="sn-lsl__detail">{source.detail}</p>
              )}
              <ul className="sn-lsl__list">
                {LIVE_CHECKLIST.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <button
          className="kr-action kr-action--primary kr-action--hero"
          type="submit"
          disabled={busy || liveBlocked}
        >
          {busy ? 'Starting session' : liveBlocked ? 'Waiting for amplifier' : 'Begin baseline'}
          <FiArrowUpRight aria-hidden="true" />
        </button>

        {error && (
          <p className="kr-error" role="alert">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
