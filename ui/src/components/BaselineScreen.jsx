// Resting-baseline recording: poll progress ~1 Hz, hand off when done.
// Every poll also lets the backend take a baseline load sample, so polling
// here is part of the measurement, not just cosmetics.
import { useRef, useState } from 'react';
import { getBaselineStatus } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import '../styles/session.css';

export default function BaselineScreen({ sessionId, seconds, onDone }) {
  const [progress, setProgress] = useState(0);
  const firedRef = useRef(false); // onDone must fire once, not once per poll

  usePoll(
    async () => {
      try {
        const st = await getBaselineStatus(sessionId);
        setProgress(st.progress);
        if (st.done && !firedRef.current) {
          firedRef.current = true;
          onDone();
        }
      } catch {
        // A missed poll keeps the last painted progress; the next one catches up.
      }
    },
    1000,
    true
  );

  const remaining = Math.max(0, Math.ceil(seconds * (1 - progress)));

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
          {remaining > 0 ? `About ${remaining} s left` : 'Computing baseline'}
        </p>
      </div>
    </div>
  );
}
