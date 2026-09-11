// The patient's display: a tablet or second screen facing the patient
// (team call, 2026-09-11). It knows as little as possible - the phase and
// the current stimulus - and shows one calm thing at a time. No answers,
// no numbers, no controls; everything measured stays on the clinician side.
import { useState } from 'react';
import { getPatientView } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import Wordmark from './Wordmark.jsx';
import '../styles/session.css';

const CALM = {
  baseline: 'Sit still, relax, and keep your eyes open.',
  waiting: 'One moment.',
  ended: 'All done. Thank you.',
};

export default function PatientScreen({ sessionId }) {
  const [view, setView] = useState({ phase: 'waiting' });

  usePoll(
    async () => {
      try {
        setView(await getPatientView(sessionId));
      } catch {
        // Keep the last state; a missed poll must never flash an error at a patient.
      }
    },
    500,
    true
  );

  return (
    <div className="pt-screen">
      {view.phase === 'task' && view.image ? (
        <img className="pt-stimulus" src={view.image} alt="Test item" />
      ) : view.phase === 'task' ? (
        <p className="pt-message">Listen to the examiner.</p>
      ) : (
        <p className="pt-message">{CALM[view.phase] || CALM.waiting}</p>
      )}
      <div className="pt-foot">
        <Wordmark />
      </div>
    </div>
  );
}
