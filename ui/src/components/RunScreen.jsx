// The clinician run screen: administer one task at a time.
// Flow per task: read prompt -> Start (stopwatch + live load) -> score it
// (Right / Wrong / Timeout) -> see what the system did -> Next task.
// The between-task beat is deliberate: the adaptation IS the product, so the
// clinician gets one quiet line telling them what just happened before the
// next prompt replaces it.
import { useEffect, useRef, useState } from 'react';
import { FiArrowRight, FiCheck, FiClock, FiPlay, FiX } from 'react-icons/fi';
import { getLiveLoad, getNextTask, postAnswer, errorText, isConflict } from '../api.js';
import usePoll from '../hooks/usePoll.js';
import '../styles/session.css';

const ACTION_COPY = {
  advance: (l) => `Raising difficulty to level ${l}`,
  hold: (l) => `Holding at level ${l}`,
  ease: (l) => `Easing to level ${l}`,
  flag: (l) => `Wrong without effort. Holding level ${l}, flagged as possible disengagement`,
};

const RESULT_COPY = { correct: 'Marked right', incorrect: 'Marked wrong', timeout: 'Marked timeout' };

export default function RunScreen({ session, onFinished }) {
  const [task, setTask] = useState(null);
  const [stage, setStage] = useState('reading'); // reading | running | submitted
  const [outcome, setOutcome] = useState(null); // answer response, shown between tasks
  const [lastResult, setLastResult] = useState('');
  const [live, setLive] = useState(null); // {load, trusted}
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const t0Ref = useRef(0);

  const fetchTask = async () => {
    try {
      setTask(await getNextTask(session.id));
    } catch (e) {
      // 409 = the session already ended (task cap); that is a finish, not a failure.
      if (isConflict(e)) onFinished();
      else setError(errorText(e));
    }
  };

  useEffect(() => {
    fetchTask();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stopwatch display. Elapsed sent to the API is computed from t0 at press
  // time, never from this 100 ms display state, so precision does not depend
  // on render cadence.
  useEffect(() => {
    if (stage !== 'running') return undefined;
    const id = setInterval(() => setElapsed((Date.now() - t0Ref.current) / 1000), 100);
    return () => clearInterval(id);
  }, [stage]);

  // Live load only while the patient is actually working: the backend buffers
  // every polled sample into the current task's load, so polling outside the
  // task window would contaminate the measurement with idle chatter.
  usePoll(
    async () => {
      try {
        setLive(await getLiveLoad(session.id));
      } catch {
        // Keep the last good reading; the next poll catches up.
      }
    },
    1000,
    stage === 'running'
  );

  const start = () => {
    t0Ref.current = Date.now();
    setElapsed(0);
    setStage('running');
  };

  const score = async (result) => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const resp = await postAnswer(session.id, task.task_id, result, (Date.now() - t0Ref.current) / 1000);
      // Session over? Either it converged, or this was the last task before
      // the cap (the response itself does not carry "ended"; n vs total_max does).
      if (resp.converged || task.n >= task.total_max) {
        onFinished();
        return;
      }
      setOutcome(resp);
      setLastResult(result);
      setStage('submitted');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    setTask(null);
    setOutcome(null);
    setStage('reading');
    setElapsed(0);
    await fetchTask();
  };

  return (
    <div className="sn-run kr-reveal">
      <header className="kr-header">
        <h1>{session.domain} session</h1>
        <p>Read each prompt aloud, then score the patient's answer against the expected one.</p>
      </header>

      <div className="sn-run__grid">
        <section className="kr-card">
          {task ? (
            <>
              <div className="kr-card__head">
                <h2 className="kr-cardtitle">
                  Task {task.n} of {task.total_max}
                </h2>
                <span className="kr-badge">Level {task.level}</span>
              </div>

              <div className="sn-task">
                <p className="sn-task__prompt">{task.prompt}</p>
                {/* Nested card: hairline only, no shadow (house rule). */}
                <div className="sn-answer">
                  <span className="sn-answer__label">Correct answer</span>
                  <p className="sn-answer__text">{task.answer}</p>
                </div>
              </div>

              <div className="sn-controls">
                {stage === 'reading' && (
                  <>
                    <button className="kr-action kr-action--primary" onClick={start}>
                      <FiPlay aria-hidden="true" />
                      Start task
                    </button>
                    <p className="kr-hint">Starts the stopwatch and the live load readout.</p>
                  </>
                )}

                {stage === 'running' && (
                  <>
                    <span className="sn-stopwatch" aria-label="Elapsed time">
                      {elapsed.toFixed(1)} s
                    </span>
                    <div className="sn-verdicts">
                      <button
                        className="kr-action kr-action--primary"
                        onClick={() => score('correct')}
                        disabled={busy}
                      >
                        <FiCheck aria-hidden="true" />
                        Right
                      </button>
                      <button
                        className="kr-btn sn-verdict--bad"
                        onClick={() => score('incorrect')}
                        disabled={busy}
                      >
                        <FiX aria-hidden="true" />
                        Wrong
                      </button>
                      <button
                        className="kr-btn sn-verdict--warn"
                        onClick={() => score('timeout')}
                        disabled={busy}
                      >
                        <FiClock aria-hidden="true" />
                        Timeout
                      </button>
                    </div>
                  </>
                )}

                {stage === 'submitted' && outcome && (
                  <div className="sn-outcome">
                    <p className="sn-outcome__headline">
                      {RESULT_COPY[lastResult]} · {ACTION_COPY[outcome.action](outcome.next_level)}
                    </p>
                    <p className="sn-outcome__reason">
                      Load {outcome.load.toFixed(2)}&times; baseline · decision: {outcome.reason}
                    </p>
                    <button className="kr-action kr-action--primary" onClick={next}>
                      Next task
                      <FiArrowRight aria-hidden="true" />
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            !error && (
              <div className="sn-skel" aria-hidden="true">
                <span className="sn-skel__bar" style={{ width: '40%' }} />
                <span className="sn-skel__bar" style={{ width: '90%' }} />
                <span className="sn-skel__bar" style={{ width: '75%' }} />
              </div>
            )
          )}
          {error && (
            <p className="kr-error sn-run__error" role="alert">
              {error}
            </p>
          )}
        </section>

        <section className="kr-card sn-load">
          <div className="kr-card__head">
            <h2 className="kr-cardtitle">Cognitive load</h2>
          </div>
          <div className="sn-load__body">
            {live ? (
              <>
                {/* 1 Hz updates: no count-up, no transitions - a measurement
                    should tick, not glide. aria-live stays off; announcing a
                    number every second is screen-reader noise. */}
                <span className="sn-load__value">
                  {live.load.toFixed(2)}
                  <span className="sn-load__unit">&times; baseline</span>
                </span>
                {live.trusted ? (
                  <span className="kr-chip">Signal clean</span>
                ) : (
                  <span className="kr-chip kr-chip--warn">Signal noisy, reading untrusted</span>
                )}
                {stage !== 'running' && <p className="kr-hint">Paused between tasks.</p>}
              </>
            ) : (
              <p className="kr-hint">Updates once the task starts.</p>
            )}
            <p className="sn-load__explain">
              How hard the brain is working right now, relative to this patient's own resting
              baseline. It decides the next task together with the answer.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
