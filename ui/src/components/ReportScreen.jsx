// The report screen: established level up front, the signature load-vs-level
// chart, then the task-by-task record. Chart bodies are functions of `big` so
// the inline card and the expand modal render from one source of truth
// (house pattern from the staff analytics page).
import { useEffect, useRef, useState } from 'react';
import { FiCheck, FiCopy, FiDownload, FiMaximize2, FiX } from 'react-icons/fi';
import { toBlob } from 'html-to-image';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts';
import { getReport, errorText } from '../api.js';
import { reasonCopy } from '../reasons.js';
import '../styles/report.css';

// Chart colours are JS-side constants (recharts props take literals); values
// mirror the --chart-* tokens in tokens.css. One palette on purpose: bars are
// a light tint of the staff green (a measurement, quiet), the level line is
// the full accent (the decision path, loud), amber is reserved for flagged
// no-effort answers, and the effort thresholds are neutral slate.
const BAR = '#7bb095';
const FLAG = '#f59e0b';
const LINE = '#237a4e';
const GRID = '#e6e9ee';
const TICK = '#64748b';
const BAND_LINE = '#cbd5e1';

const RESULT_PILL = {
  correct: ['kr-pill--good', 'Right'],
  incorrect: ['kr-pill--bad', 'Wrong'],
  timeout: ['kr-pill--warn', 'Timeout'],
};

const ACTION_COPY = {
  advance: 'Raised difficulty',
  hold: 'Held level',
  ease: 'Eased difficulty',
  flag: 'Flagged disengagement',
};

// House count-up: rAF + ease-out cubic, painting via a ref instead of state
// so 90 frames do not mean 90 re-renders. The real value is the initial DOM
// content, so it is correct even if the animation never runs.
function CountUp({ value, decimals = 0, suffix = '' }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const paint = (p) => {
      const e = 1 - Math.pow(1 - p, 3);
      el.textContent = `${(value * e).toFixed(decimals)}${suffix}`;
    };
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      paint(1);
      return undefined;
    }
    const dur = 1500;
    const t0 = performance.now();
    let raf = 0;
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / dur);
      paint(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, decimals, suffix]);
  return <span ref={ref}>{`${value.toFixed(decimals)}${suffix}`}</span>;
}

function Kpi({ label, sub, pill, children }) {
  return (
    <section className="kr-card rp-kpi">
      <div className="rp-kpi__labelrow">
        <span className="rp-kpi__label">{label}</span>
        {pill}
      </div>
      <span className="rp-kpi__value">{children}</span>
      <span className="rp-kpi__sub">{sub}</span>
    </section>
  );
}

// Chart card with the house hover-reveal control set: expand-to-modal,
// copy-as-image, download-as-PNG (same trio behaviour as UQwest staff
// analytics; capture via html-to-image at 2x for deck-quality pixels).
function ChartCard({ title, sub, onExpand, exportName, children }) {
  const ref = useRef(null);
  const [copied, setCopied] = useState(false);

  const snapshot = () =>
    toBlob(ref.current, {
      backgroundColor: '#ffffff',
      pixelRatio: 2,
      // The hover controls must not appear in the exported image.
      filter: (node) => !(node.classList && node.classList.contains('rp-card__ctrls')),
    });

  const copyImage = async () => {
    try {
      const blob = await snapshot();
      if (blob && navigator.clipboard?.write) {
        await navigator.clipboard.write([new window.ClipboardItem({ 'image/png': blob })]);
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      }
    } catch {
      // Capture or clipboard-image unsupported in this browser - fail quietly.
    }
  };

  const downloadImage = async () => {
    try {
      const blob = await snapshot();
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exportName;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Same quiet failure as copy.
    }
  };

  return (
    <section className="kr-card rp-card" ref={ref}>
      <div className="rp-card__ctrls">
        <button
          type="button"
          className="rp-card__ctrl"
          onClick={onExpand}
          aria-label="Expand chart"
          title="Expand"
        >
          <FiMaximize2 aria-hidden="true" />
        </button>
        <button
          type="button"
          className="rp-card__ctrl"
          onClick={downloadImage}
          aria-label="Download chart as PNG"
          title="Download PNG"
        >
          <FiDownload aria-hidden="true" />
        </button>
        <button
          type="button"
          className="rp-card__ctrl"
          onClick={copyImage}
          aria-label="Copy chart as image"
          title={copied ? 'Copied' : 'Copy chart'}
        >
          {copied ? <FiCheck aria-hidden="true" /> : <FiCopy aria-hidden="true" />}
        </button>
      </div>
      <h2 className="rp-card__title">{title}</h2>
      <p className="rp-card__sub">{sub}</p>
      {children}
    </section>
  );
}

export default function ReportScreen({ sessionId, onNewSession }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    getReport(sessionId)
      .then(setReport)
      .catch((e) => setError(errorText(e)));
  }, [sessionId]);

  // Close the expand modal on Escape and lock background scroll while open.
  useEffect(() => {
    if (!expanded) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setExpanded(false);
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [expanded]);

  if (error) {
    return (
      <div className="rp-report">
        <p className="kr-error" role="alert">
          {error}
        </p>
        <button className="kr-btn" onClick={onNewSession}>
          New session
        </button>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="rp-report" aria-hidden="true">
        <div className="rp-kpis">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="kr-card rp-kpi rp-skel" />
          ))}
        </div>
        <div className="kr-card rp-card rp-skel rp-skel--tall" />
      </div>
    );
  }

  const tasks = report.tasks;
  const nCorrect = tasks.filter((t) => t.result === 'correct').length;
  const anyFlag = tasks.some((t) => t.flag);
  const [bandLo, bandHi] = report.band;

  const chartBody = (big) => (
    <ResponsiveContainer width="100%" height={big ? 460 : 280}>
      <ComposedChart data={tasks} margin={{ top: 24, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid vertical={false} strokeDasharray="4 4" stroke={GRID} />
        <XAxis
          dataKey="n"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 12, fill: TICK }}
        />
        {/* One visible axis (load). A second labelled axis for level invited
            reading a level against the load ruler; the level line carries its
            own numbers instead, on a hidden scale so it never flattens. */}
        <YAxis
          yAxisId="load"
          axisLine={false}
          tickLine={false}
          width={40}
          // Integer ceiling: a fractional top (3.3000000000000003) leaks float
          // noise into the tick labels. Always tall enough to show the band.
          domain={[0, (dataMax) => Math.ceil(Math.max(dataMax * 1.15, bandHi * 1.1))]}
          tick={{ fontSize: 12, fill: TICK }}
        />
        <YAxis yAxisId="level" hide domain={[0.5, report.level_max + 0.5]} />
        {/* Effort thresholds, not a data region: full-width dashed lines
            (a ReferenceArea on a category axis stops at the category centres). */}
        <ReferenceLine yAxisId="load" y={bandLo} stroke={BAND_LINE} strokeDasharray="6 4" />
        <ReferenceLine yAxisId="load" y={bandHi} stroke={BAND_LINE} strokeDasharray="6 4" />
        {/* Entry animation only in the expand modal (big): there the layout is
            stable and the grow/draw reveal plays reliably, house-style. On the
            report's first mount the same animation races the container measure
            and can leave bars unpainted and the line dash-hidden, so inline
            renders static. */}
        <Bar
          yAxisId="load"
          dataKey="load"
          radius={[6, 6, 0, 0]}
          maxBarSize={big ? 72 : 44}
          isAnimationActive={big}
        >
          {tasks.map((t) => (
            <Cell key={t.n} fill={t.flag ? FLAG : BAR} />
          ))}
          <LabelList
            dataKey="load"
            position="top"
            formatter={(v) => v.toFixed(2)}
            style={{ fontSize: 12, fontWeight: 700, fill: '#0f172a' }}
          />
        </Bar>
        <Line
          yAxisId="level"
          type="linear"
          dataKey="level"
          stroke={LINE}
          strokeWidth={2.5}
          dot={{ r: 4, fill: '#ffffff', stroke: LINE, strokeWidth: 2 }}
          isAnimationActive={big}
        >
          <LabelList
            dataKey="level"
            position="top"
            offset={10}
            style={{ fontSize: 11, fontWeight: 700, fill: LINE }}
          />
        </Line>
      </ComposedChart>
    </ResponsiveContainer>
  );

  const legend = (
    <ul className="rp-legend">
      <li>
        <span className="rp-legend__swatch" style={{ background: BAR }} />
        Cognitive load (multiple of baseline)
      </li>
      {anyFlag && (
        <li>
          <span className="rp-legend__swatch" style={{ background: FLAG }} />
          Flagged: wrong without effort
        </li>
      )}
      <li>
        <span className="rp-legend__line" style={{ background: LINE }} />
        Task difficulty level
      </li>
      <li>
        <span className="rp-legend__dash" />
        Target effort band ({bandLo.toFixed(1)} to {bandHi.toFixed(1)})
      </li>
    </ul>
  );

  const chartSub =
    'Bars: load per task, multiple of resting baseline. Line: difficulty level, labelled at each point.';

  return (
    <div className="rp-report">
      <header className="kr-header rp-header kr-reveal">
        <div>
          <h1>Assessment report</h1>
          <p>
            {report.domain} · {report.patient_ref} · {report.date} · {tasks.length} tasks
          </p>
        </div>
        <button className="kr-btn" onClick={onNewSession}>
          New session
        </button>
      </header>

      {report.disengaged_count > 0 && (
        <p className="kr-chip kr-chip--warn rp-flagnote kr-reveal">
          {report.disengaged_count} answer{report.disengaged_count === 1 ? '' : 's'} flagged: wrong
          without measurable effort. That reads as disengagement, not deficit.
        </p>
      )}

      <div className="rp-kpis kr-reveal kr-reveal--2">
        <Kpi
          label="Established level"
          sub={report.reason}
          pill={
            report.converged ? (
              <span className="kr-pill kr-pill--good">Converged</span>
            ) : (
              <span className="kr-pill kr-pill--idle">Did not converge</span>
            )
          }
        >
          {/* "of 5" keeps the scale visible: a bare "Level 1" reads as a bad
              outcome instead of a position on a 5-point instrument. */}
          Level <CountUp value={report.final_level} />{' '}
          <span className="rp-kpi__scale">of {report.level_max}</span>
        </Kpi>
        <Kpi label="Accuracy" sub={`${nCorrect} of ${tasks.length} tasks right`}>
          <CountUp value={Math.round(report.accuracy * 100)} suffix="%" />
        </Kpi>
        <Kpi label="Avg time to answer" sub="Timeouts excluded">
          {report.mean_rt == null ? 'Not measured' : <CountUp value={report.mean_rt} decimals={1} suffix=" s" />}
        </Kpi>
        <Kpi
          label="Flagged answers"
          sub={report.disengaged_count > 0 ? 'Wrong with no effort behind it' : 'None flagged'}
        >
          <CountUp value={report.disengaged_count} />
        </Kpi>
      </div>

      <div className="kr-reveal kr-reveal--3">
        <ChartCard
          title="Load and difficulty, task by task"
          sub={chartSub}
          onExpand={() => setExpanded(true)}
          exportName={`kaira_${report.patient_ref}_load.png`}
        >
          {chartBody(false)}
          {legend}
        </ChartCard>
      </div>

      <section className="kr-card rp-tablecard kr-reveal kr-reveal--4">
        <div className="kr-card__head">
          <h2 className="kr-cardtitle">Task record</h2>
          <span className="kr-badge">{tasks.length} tasks</span>
        </div>
        <div className="rp-tablewrap">
          <table className="rp-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Task</th>
                <th>Level</th>
                <th>Result</th>
                <th>Load</th>
                <th>Time</th>
                <th>System response</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => {
                const [pillClass, pillText] = RESULT_PILL[t.result];
                return (
                  <tr key={t.n} className={t.flag ? 'rp-row--flag' : undefined}>
                    <td data-label="#">{t.n}</td>
                    <td data-label="Task" className="rp-taskid">
                      {t.task_id}
                    </td>
                    <td data-label="Level">{t.level}</td>
                    <td data-label="Result">
                      <span className={`kr-pill ${pillClass}`}>{pillText}</span>
                      {t.flag && <span className="kr-chip kr-chip--warn rp-flagchip">Disengaged</span>}
                    </td>
                    <td data-label="Load" className="rp-num">
                      {t.load.toFixed(2)}&times;{!t.trusted && ' (untrusted)'}
                    </td>
                    <td data-label="Time" className="rp-num">
                      {t.rt.toFixed(1)} s
                    </td>
                    <td data-label="System response">
                      <span className="rp-response">
                        {ACTION_COPY[t.action] || t.action}
                        <span className="rp-reason">{reasonCopy(t.reason)}</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* The quiet line that answers "is this a diagnosis?" before a judge
          or clinician has to ask it. */}
      <p className="rp-disclaimer kr-reveal kr-reveal--4">
        Load is measured against this patient's own resting baseline. Values are not comparable
        between patients, and this report is a measurement, not a diagnostic output.
      </p>

      {/* Expand modal: same chart, large. Click backdrop or Esc to close. */}
      {expanded && (
        <div
          className="rp-modal"
          role="dialog"
          aria-modal="true"
          aria-label="Load and difficulty, task by task"
          onClick={() => setExpanded(false)}
        >
          <div className="rp-modal__panel" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="rp-modal__close"
              onClick={() => setExpanded(false)}
              aria-label="Close"
            >
              <FiX aria-hidden="true" />
            </button>
            <h2 className="rp-card__title">Load and difficulty, task by task</h2>
            <p className="rp-card__sub">{chartSub}</p>
            {chartBody(true)}
            {legend}
          </div>
        </div>
      )}
    </div>
  );
}
