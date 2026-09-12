// The patient's display: a tablet or second screen facing the patient.
// It knows as little as possible - the phase and the current stimulus -
// and shows one calm thing at a time. No answers, no numbers, no controls.
//
// Auto-attach: with no session id it waits, polling for the newest running
// session, and springs to life the moment the clinician begins - so the
// iPad can sit on ?role=patient all day. When a session ends it goes back
// to waiting, ready for the next one.
import { useState } from 'react';
import { getCurrentSession, getPatientView } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import Wordmark from './Wordmark.jsx';
import '../styles/session.css';

const CALM = {
  idle: 'Waiting for the session to begin.',
  baseline: 'Sit still, relax, and keep your eyes open.',
  waiting: 'One moment.',
  ended: 'All done. Thank you.',
};

export default function PatientScreen({ sessionId = null }) {
  const [sid, setSid] = useState(sessionId);
  const [view, setView] = useState({ phase: 'idle' });

  const attached = sid != null;
  const over = view.phase === 'ended';

  // Look for the newest running session while unattached, and again once
  // this one has finished (a fixed ?patient=<id> link opts out of that).
  usePoll(
    async () => {
      try {
        const current = await getCurrentSession();
        if (current && current !== sid) {
          setSid(current);
          setView({ phase: 'waiting' });
        }
      } catch {
        // The API may not be up yet; keep waiting calmly.
      }
    },
    1500,
    !sessionId && (!attached || over)
  );

  usePoll(
    async () => {
      try {
        setView(await getPatientView(sid));
      } catch {
        // Keep the last state; a missed poll must never flash an error at a patient.
      }
    },
    500,
    attached
  );

  return (
    <div className="pt-screen">
      {attached && view.phase === 'task' && view.image ? (
        <img className="pt-stimulus" src={view.image} alt="Test item" />
      ) : attached && view.phase === 'task' ? (
        <p className="pt-message">Listen to the examiner.</p>
      ) : (
        <p className="pt-message">{CALM[attached ? view.phase : 'idle'] || CALM.waiting}</p>
      )}
      <div className="pt-foot">
        <Wordmark />
      </div>
    </div>
  );
}
