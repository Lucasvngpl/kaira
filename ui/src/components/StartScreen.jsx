// New-assessment form: patient reference + domain, then hand off to baseline.
import { useState } from 'react';
import { FiArrowRight } from 'react-icons/fi';
import { startSession, errorText } from '../api.js';
import '../styles/session.css';

export default function StartScreen({ info, onStarted }) {
  const [patientRef, setPatientRef] = useState('');
  const [domain, setDomain] = useState('Memory');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // Until GET / answers, offer the one domain we know is populated rather
  // than an empty select.
  const domains = info ? Object.entries(info.domains) : [['Memory', true]];

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

        <button className="kr-action kr-action--primary" type="submit" disabled={busy}>
          {busy ? 'Starting session' : 'Begin baseline'}
          <FiArrowRight aria-hidden="true" />
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
