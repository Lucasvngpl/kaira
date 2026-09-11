// Shell + phase state machine. One session is a linear flow
// (start -> baseline -> run -> report), so screens are swapped on local state
// rather than routed: a URL you could deep-link into the middle of a live
// EEG session is a foot-gun, not a feature, and this app has no second flow.
import { useState } from 'react';
import { getRoot } from './api.js';
import usePoll from './hooks/usePoll.js';
import Wordmark from './components/Wordmark.jsx';
import PatientScreen from './components/PatientScreen.jsx';
import StartScreen from './components/StartScreen.jsx';
import BaselineScreen from './components/BaselineScreen.jsx';
import RunScreen from './components/RunScreen.jsx';
import ReportScreen from './components/ReportScreen.jsx';

// ?demo=report deep-links straight to the report screen with sample data
// (see sampleReport.js) - for UI work and reveal checks without running a
// 15 s baseline plus a full session. Read once; the state machine owns the
// rest of the navigation.
const DEMO = new URLSearchParams(window.location.search).get('demo');

// ?patient=<session id> turns this tab into the patient's display - the one
// sanctioned deep link, because the second screen must be able to join a
// session that is already running.
const PATIENT_SESSION = new URLSearchParams(window.location.search).get('patient');

// The patient display is its own tiny app: no topbar, no state machine.
// Split at the top level (not an early return) so ClinicianApp's hooks
// stay unconditional - the rules of hooks are part of the house style.
export default function App() {
  return PATIENT_SESSION ? <PatientScreen sessionId={PATIENT_SESSION} /> : <ClinicianApp />;
}

function ClinicianApp() {
  const [phase, setPhase] = useState(DEMO === 'report' ? 'report' : 'start'); // start | baseline | run | report
  const [session, setSession] = useState(null); // {id, baselineSeconds, patientRef, domain}
  const [baseline, setBaseline] = useState(null); // {stable, seconds} from the finished baseline
  const [info, setInfo] = useState(null); // GET / : {synthetic, domains}
  const [infoError, setInfoError] = useState('');

  // Keep knocking until the API answers (it may start, or restart, after the
  // UI): a one-shot check leaves a stale "not reachable" banner that only a
  // manual refresh clears. Polling stops once the API has been seen.
  usePoll(
    async () => {
      try {
        setInfo(await getRoot());
        setInfoError('');
      } catch {
        setInfoError('API not reachable on port 8300. Start it with: python api/main.py');
      }
    },
    2000,
    !info
  );

  const startOver = () => {
    setPhase('start');
    setSession(null);
    setBaseline(null);
  };

  return (
    <div className="kr-page">
      <div className="kr-topbar">
        <Wordmark />
        <div className="kr-topbar__meta">
          {session && (
            <span>
              {session.patientRef} · {session.domain}
            </span>
          )}
          {/* Opens the patient-facing display in its own tab, to be dragged
              onto the tablet / second screen. Live phases only. */}
          {session && phase !== 'report' && (
            <a className="kr-btn" href={`?patient=${session.id}`} target="_blank" rel="noreferrer">
              Patient screen
            </a>
          )}
          {/* A clinician must never mistake a demo for a recording, so the
              warning rides every LIVE screen. The report is the finished
              document: its provenance belongs to the report content, not to
              whatever mode the API happens to be in while viewing it. */}
          {info?.synthetic && phase !== 'report' && (
            <span
              className="kr-chip kr-chip--demo"
              title="Numbers come from generated noise, not a patient. Disappears when a real amplifier is connected."
            >
              Demo signal
            </span>
          )}
        </div>
      </div>

      {infoError && phase === 'start' && (
        <p className="kr-error kr-error--banner" role="alert">
          {infoError}
        </p>
      )}

      {phase === 'start' && (
        <StartScreen
          info={info}
          onStarted={(s) => {
            setSession(s);
            setPhase('baseline');
          }}
        />
      )}
      {phase === 'baseline' && (
        <BaselineScreen
          sessionId={session.id}
          seconds={session.baselineSeconds}
          canSkip={info?.synthetic}
          onDone={(result) => {
            setBaseline(result);
            setPhase('run');
          }}
        />
      )}
      {phase === 'run' && (
        <RunScreen
          session={session}
          baseline={baseline}
          band={info?.band}
          onFinished={() => setPhase('report')}
        />
      )}
      {phase === 'report' && (
        <ReportScreen
          sessionId={session?.id}
          demo={DEMO === 'report' && !session}
          onNewSession={startOver}
        />
      )}
    </div>
  );
}
