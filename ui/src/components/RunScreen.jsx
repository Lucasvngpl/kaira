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

const RESULT_COPY = { correct: 'Marked right', incorrect: 'Marked wrong', timeout: 'Marked timeout' };

// 5-segment effort meter. The fill count comes from the server (decide.py
// derives it from the same constants as the rule) - the UI computes nothing.
function EffortMeter({ bars }) {
  return (
    <div className={`sn-meter${bars == null ? ' sn-meter--off' : ''}`} aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={`sn-meter__seg${bars != null && i <= bars ? ' sn-meter__seg--on' : ''}`} />
      ))}
    </div>
  );
}

// Live-load sampling: 4 Hz (matches the real pipeline's 250 ms window step),
// keeping a rolling ~30 s window. The first 2 s of a task show a warm-up
// state instead of a number: a real instrument settles before it reads.
const POLL_MS = 250;
const SPARK_CAP = 120; // 30 s at 4 Hz
const WARMUP_S = 2;

// Hand-authored SVG sparkline (house rule: recharts is for report charts,
// everything live is hand-drawn). Untrusted windows break the line and drop
// a grey dot instead of silently interpolating: the gap IS the quality gate,
// visible. No smoothing on purpose: real load estimates jitter, and jitter
// reads as live.
function LoadSparkline({ samples, band, paused }) {
  const W = 260;
  const H = 64;
  const yMax = Math.max(band[1] * 1.2, ...samples.map((s) => s.load * 1.1), 1);
  const y = (v) => H - (v / yMax) * H;
  const x = (i) => (i / (SPARK_CAP - 1)) * W;

  const segments = [];
  const rejects = [];
  let current = [];
  samples.forEach((s, i) => {
    if (s.trusted) {
      current.push(`${x(i).toFixed(1)},${y(s.load).toFixed(1)}`);
    } else {
      if (current.length) segments.push(current);
      current = [];
      rejects.push({ i, load: s.load });
    }
  });
  if (current.length) segments.push(current);

  return (
    <svg
      className={`sn-spark${paused ? ' sn-spark--paused' : ''}`}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <rect
        className="sn-spark__band"
        x="0"
        y={y(band[1])}
        width={W}
        height={Math.max(0, y(band[0]) - y(band[1]))}
      />
      {segments.map((pts, k) => (
        <polyline key={k} className="sn-spark__line" points={pts.join(' ')} vectorEffect="non-scaling-stroke" />
      ))}
      {rejects.map((r) => (
        <circle key={r.i} className="sn-spark__reject" cx={x(r.i)} cy={y(r.load)} r="1.8" />
      ))}
    </svg>
  );
}

export default function RunScreen({ session, band = [0.67, 1.5], onFinished }) {
  // band prop comes from GET /; the literal is only a render fallback while
  // that first fetch is in flight.
  const [task, setTask] = useState(null);
  const [stage, setStage] = useState('reading'); // reading | running | submitted
  const [outcome, setOutcome] = useState(null); // answer response, shown between tasks
  const [lastResult, setLastResult] = useState('');
  const [live, setLive] = useState(null); // {load, trusted}, most recent sample
  const [samples, setSamples] = useState([]); // rolling window for the sparkline
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
        const sample = await getLiveLoad(session.id);
        setLive(sample);
        setSamples((prev) => [...prev, sample].slice(-SPARK_CAP));
      } catch {
        // Keep the last good reading; the next poll catches up.
      }
    },
    POLL_MS,
    stage === 'running'
  );

  const start = () => {
    t0Ref.current = Date.now();
    setElapsed(0);
    setSamples([]); // the sparkline shows THIS task's read, not the last one's
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
                    {/* The WHY leads, and the sentence comes from decide.py
                        itself - the UI never invents clinical wording. */}
                    <p className="sn-outcome__headline">{outcome.reason_text}</p>
                    <p className="sn-outcome__reason">
                      {RESULT_COPY[lastResult]} · Load {outcome.load.toFixed(2)}&times; baseline
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
            {/* While the stopwatch runs this number IS the EEG doing
                something; the pulse says "live measurement", not decoration. */}
            {stage === 'running' && <span className="sn-load__live">Live</span>}
          </div>
          <div className="sn-load__body">
            {stage === 'running' && elapsed < WARMUP_S ? (
              // No window yet: a real instrument settles before it reads.
              <span className="sn-load__warmup">Measuring&hellip;</span>
            ) : live ? (
              <>
                {/* 4 Hz updates: no count-up, no transitions - a measurement
                    should tick, not glide. aria-live stays off; announcing a
                    number four times a second is screen-reader noise. */}
                <span
                  className={`sn-load__value${stage === 'running' ? '' : ' sn-load__value--paused'}`}
                >
                  {live.load.toFixed(2)}
                  <span className="sn-load__unit">&times; baseline</span>
                </span>
                <EffortMeter bars={stage === 'running' ? live.bars : null} />
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
            {samples.length > 1 && (
              <LoadSparkline samples={samples} band={band} paused={stage !== 'running'} />
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
