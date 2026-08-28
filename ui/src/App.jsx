// Shell + phase state machine. One session is a linear flow
// (start -> baseline -> run -> report), so screens are swapped on local state
// rather than routed: a URL you could deep-link into the middle of a live
// EEG session is a foot-gun, not a feature, and this app has no second flow.
import { useState } from 'react';
import { getRoot } from './api.js';
import usePoll from './hooks/usePoll.js';
import StartScreen from './components/StartScreen.jsx';
import BaselineScreen from './components/BaselineScreen.jsx';
import RunScreen from './components/RunScreen.jsx';
import ReportScreen from './components/ReportScreen.jsx';

// ?demo=report deep-links straight to the report screen with sample data
// (see sampleReport.js) - for UI work and reveal checks without running a
// 15 s baseline plus a full session. Read once; the state machine owns the
// rest of the navigation.
const DEMO = new URLSearchParams(window.location.search).get('demo');

export default function App() {
  const [phase, setPhase] = useState(DEMO === 'report' ? 'report' : 'start'); // start | baseline | run | report
  const [session, setSession] = useState(null); // {id, baselineSeconds, patientRef, domain}
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
  };

  return (
    <div className="kr-page">
      <div className="kr-topbar">
        <span className="kr-wordmark">Kaira</span>
        <div className="kr-topbar__meta">
          {session && (
            <span>
              {session.patientRef} · {session.domain}
            </span>
          )}
          {/* A clinician must never mistake a demo for a recording, so the
              warning rides every LIVE screen. The report is the finished
              document: its provenance belongs to the report content, not to
              whatever mode the API happens to be in while viewing it. */}
          {info?.synthetic && phase !== 'report' && (
            <span className="kr-chip kr-chip--warn">Synthetic signal</span>
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
          onDone={() => setPhase('run')}
        />
      )}
      {phase === 'run' && (
        <RunScreen session={session} band={info?.band} onFinished={() => setPhase('report')} />
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
