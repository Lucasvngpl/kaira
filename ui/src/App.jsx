// Shell + phase state machine. One session is a linear flow
// (start -> baseline -> run -> report), so screens are swapped on local state
// rather than routed: a URL you could deep-link into the middle of a live
// EEG session is a foot-gun, not a feature, and this app has no second flow.
import { useEffect, useState } from 'react';
import { getRoot } from './api.js';
import StartScreen from './components/StartScreen.jsx';
import BaselineScreen from './components/BaselineScreen.jsx';
import RunScreen from './components/RunScreen.jsx';
import ReportScreen from './components/ReportScreen.jsx';

export default function App() {
  const [phase, setPhase] = useState('start'); // start | baseline | run | report
  const [session, setSession] = useState(null); // {id, baselineSeconds, patientRef, domain}
  const [info, setInfo] = useState(null); // GET / : {synthetic, domains}
  const [infoError, setInfoError] = useState('');

  useEffect(() => {
    getRoot()
      .then(setInfo)
      .catch(() => setInfoError('API not reachable on port 8300. Start it with: python api/main.py'));
  }, []);

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
          {/* A clinician must never mistake a demo for a recording; say so on
              every screen, not in a settings page nobody opens. */}
          {info?.synthetic && <span className="kr-chip kr-chip--warn">Synthetic signal</span>}
        </div>
      </div>

      {infoError && phase === 'start' && (
        <p className="kr-error" role="alert">
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
        <RunScreen session={session} onFinished={() => setPhase('report')} />
      )}
      {phase === 'report' && <ReportScreen sessionId={session.id} onNewSession={startOver} />}
    </div>
  );
}
