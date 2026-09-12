// Resting-baseline recording: poll progress once a second, hand off when
// done. Each poll also makes the backend take one baseline sample, so this
// polling IS the measurement - stop polling and the baseline goes deaf.
import { useRef, useState } from 'react';
import { getBaselineStatus, skipBaseline, errorText } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import '../styles/session.css';

export default function BaselineScreen({ sessionId, seconds, canSkip, onDone }) {
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const firedRef = useRef(false); // onDone must fire once, not once per poll

  // Hand the outcome up: how long it really ran, and whether the signal
  // ever settled (RunScreen warns the clinician when not).
  const finish = (st) => {
    if (!firedRef.current) {
      firedRef.current = true;
      onDone({ stable: st.stable, seconds: st.seconds });
    }
  };

  usePoll(
    async () => {
      try {
        const st = await getBaselineStatus(sessionId);
        setProgress(st.progress);
        if (st.done) finish(st);
      } catch {
        // A missed poll keeps the last painted progress; the next one catches up.
      }
    },
    1000,
    true
  );

  const skip = async () => {
    try {
      finish(await skipBaseline(sessionId));
    } catch (e) {
      // The baseline keeps running either way, but the click must never
      // look dead - say why the server refused.
      setError(errorText(e));
    }
  };

  const remaining = Math.max(0, Math.ceil(seconds * (1 - progress)));
  // "About 2:54 left" reads better than "About 174 s left" now that the
  // protocol baseline is three minutes; short rehearsal baselines keep seconds.
  const remainingText =
    remaining >= 60
      ? `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`
      : `${remaining} s`;

  return (
    <div className="sn-baseline kr-reveal">
      <div className="kr-card sn-baseline__card" role="status" aria-live="polite">
        <h2 className="sn-baseline__title">Recording resting baseline</h2>
        <p className="sn-baseline__sub">
          Ask the patient to sit still, relax, and keep their eyes open. The first task starts
          automatically.
        </p>
        <div className="sn-progress" aria-hidden="true">
          <span className="sn-progress__fill" style={{ width: `${progress * 100}%` }} />
        </div>
        <p className="sn-baseline__count">
          {remaining > 0 ? `Up to ${remainingText} left` : 'Computing baseline'}
        </p>
        {/* Only the real protocol adapts; short rehearsal baselines just run out. */}
        {seconds > 90 && <p className="kr-hint">Ends early once the signal settles.</p>}
        {/* Demo-only escape hatch for UI testing; the server refuses it on
            real hardware, so a patient session can never lose its baseline. */}
        {canSkip && (
          <button className="kr-btn" onClick={skip}>
            Skip baseline (demo)
          </button>
        )}
        {error && (
          <p className="kr-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
