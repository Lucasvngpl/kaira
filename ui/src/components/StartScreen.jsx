// New-assessment form, plus the signal-source switch (Test vs Live, where
// only the real EE511 amp counts) and the patient-screen QR.
import { useEffect, useState } from 'react';
import { FiArrowUpRight } from 'react-icons/fi';
import QRCode from 'qrcode';
import {
  startSession, getStreamStatus, setStreamMode, getStreamList,
  getNetInfo, getPatientStatus, errorText,
} from '../api.js';
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
  const [streams, setStreams] = useState(null); // /stream/list, on demand
  const [scanning, setScanning] = useState(false);
  const [qr, setQr] = useState(null); // {img, url} for the patient entrance
  const [patientOn, setPatientOn] = useState(false);

  // The QR encodes THIS ui served at the machine's LAN address, so any
  // device on the hotspot lands straight on the patient screen.
  useEffect(() => {
    (async () => {
      try {
        const { ip } = await getNetInfo();
        const url = `http://${ip}:${window.location.port || 80}/?role=patient`;
        setQr({ img: await QRCode.toDataURL(url, { margin: 1, width: 360 }), url });
      } catch {
        // API not up yet; the banner covers it, and we retry via the poll below.
      }
    })();
  }, []);

  usePoll(
    async () => {
      try {
        setPatientOn((await getPatientStatus()).connected);
        if (!qr) {
          const { ip } = await getNetInfo();
          const url = `http://${ip}:${window.location.port || 80}/?role=patient`;
          setQr({ img: await QRCode.toDataURL(url, { margin: 1, width: 360 }), url });
        }
      } catch {
        setPatientOn(false);
      }
    },
    2000,
    true
  );

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

  const pickMode = async (mode, name = null) => {
    setSource((s) => ({ ...(s || {}), mode, selected: name, connected: false, detail: 'connecting...' }));
    try {
      setSource(await setStreamMode(mode, name));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const scan = async () => {
    setScanning(true);
    try {
      setStreams(await getStreamList()); // ~3 s: the server scans the whole network
    } catch (e) {
      setError(errorText(e));
    } finally {
      setScanning(false);
    }
  };

  const liveBlocked = source?.mode === 'live' && !source?.connected;
  const blocked = liveBlocked || !patientOn;

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

      <div className="sn-start__row">
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
          <div className="sn-streams">
            <button type="button" className="kr-btn" onClick={scan} disabled={scanning}>
              {scanning ? 'Scanning…' : 'Scan for streams'}
            </button>
            {streams && (
              <select
                aria-label="Pick a specific stream"
                value={source?.selected || ''}
                onChange={(e) => pickMode(source?.mode || 'test', e.target.value || null)}
              >
                <option value="">Auto ({source?.mode === 'live' ? 'EE511 only' : 'any stream, else synthetic'})</option>
                {streams.map((st) => (
                  <option key={st.name} value={st.name}>
                    {st.name} · {st.channels} ch · {st.srate} Hz · {st.host}
                  </option>
                ))}
              </select>
            )}
            {streams && streams.length === 0 && <p className="kr-hint">No LSL streams visible.</p>}
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
          disabled={busy || blocked}
        >
          {busy
            ? 'Starting session'
            : liveBlocked
              ? 'Waiting for amplifier'
              : !patientOn
                ? 'Waiting for patient screen'
                : 'Begin baseline'}
          <FiArrowUpRight aria-hidden="true" />
        </button>

        {error && (
          <p className="kr-error" role="alert">
            {error}
          </p>
        )}
      </form>

      <aside className="kr-card sn-qr">
        <div className="kr-card__head" style={{ padding: 0 }}>
          <h2 className="kr-cardtitle">Patient screen</h2>
          {patientOn ? (
            <span className="kr-chip"><i />Connected</span>
          ) : (
            <span className="kr-chip kr-chip--warn">Not connected</span>
          )}
        </div>
        {qr ? (
          <>
            <img src={qr.img} alt="QR code that opens the patient screen" />
            <p className="kr-hint">
              Scan on any device on this network. It becomes the patient's display and the
              session can start.
            </p>
            <p className="sn-qr__url">{qr.url}</p>
          </>
        ) : (
          <p className="kr-hint">Waiting for the server to report its address&hellip;</p>
        )}
      </aside>
      </div>
    </div>
  );
}
