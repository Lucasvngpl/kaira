// The report screen: established level up front, the signature load-vs-level
// chart, then the task-by-task record. Chart bodies are functions of `big` so
// the inline card and the expand modal render from one source of truth
// (house pattern from the staff analytics page).
import { useEffect, useRef, useState } from 'react';
import { FiCheck, FiCopy, FiDownload, FiMaximize2, FiX } from 'react-icons/fi';
import { toBlob } from 'html-to-image';
import {
  Bar,
  Cell,
  ComposedChart,
  LabelList,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts';
import { getReport, errorText } from '../api.js';
import { reasonCopy } from '../reasons.js';
import { SAMPLE_REPORT } from '../sampleReport.js';
import '../styles/report.css';

// Chart colours are JS-side constants (recharts props take literals); values
// mirror the --chart-* tokens in tokens.css. One palette on purpose: bars are
// a light tint of the staff green (a measurement, quiet), the level line is
// the full accent (the decision path, loud), amber is reserved for flagged
// no-effort answers, and the effort thresholds are neutral slate.
const BAR = '#7bb095';
const FLAG = '#f59e0b';
const LINE = '#237a4e';
// Axis text and lines in clean ink (DM Sans comes from the page cascade
// plus the .rp-report .recharts-text rule): the sketch is a black pen
// drawing, not a grey one.
const TICK = '#0a1729';
const AXIS = '#0a1729';

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

// Task kinds -> clinician-facing names; the machine id stays as a small
// second line for cross-referencing with tasks.py.
const KIND_COPY = {
  word_list: 'Word recall',
  digit_span: 'Digit span',
  digit_span_backward: 'Digit span, reverse',
  paired_associates: 'Paired associates',
};

// mem_l3_001 -> "Item 1": the clinician cares which stimulus from the level's
// bank was used (repeat visits, practice effects), not our file coordinates.
// The raw id still travels in the report JSON for engineers.
const taskItem = (id) => {
  const m = /_l\d+_(\d+)$/.exec(id);
  return m ? `Item ${parseInt(m[1], 10)}` : id;
};

// One sentence, two homes: the report foot and the expand modal, so the
// screenshot-able artifact carries the non-diagnostic framing with it.
const DISCLAIMER =
  "Load is measured against this patient's own resting baseline. Values are not comparable " +
  'between patients, and this report is a measurement, not a diagnostic output.';

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

export default function ReportScreen({ sessionId, onNewSession, demo = false }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (demo) {
      setReport(SAMPLE_REPORT); // ?demo=report: fabricated PT-SAMPLE data, no session behind it
      return;
    }
    getReport(sessionId)
      .then(setReport)
      .catch((e) => setError(errorText(e)));
  }, [sessionId, demo]);

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

  // Level numeral rendered only at the start of a run (first task, or the
  // level moved); recharts hands us the point's x/y and datum index.
  const levelChangeLabel = ({ x, y, value, index }) => {
    if (index > 0 && tasks[index - 1].level === value) return null;
    return (
      <text
        x={x}
        y={y - 12}
        textAnchor="middle"
        style={{
          fontSize: 11,
          fontWeight: 700,
          fill: LINE,
          stroke: '#ffffff',
          strokeWidth: 3,
          paintOrder: 'stroke',
        }}
      >
        {value}
      </text>
    );
  };

  const chartBody = (big) => (
    <ResponsiveContainer width="100%" height={big ? 460 : 280}>
      <ComposedChart data={tasks} margin={{ top: 24, right: 8, left: 8, bottom: 14 }}>
        <XAxis
          dataKey="n"
          axisLine={{ stroke: AXIS }}
          tickLine={false}
          tick={{ fontSize: 12, fill: TICK }}
          label={{ value: 'Question number', position: 'insideBottom', offset: -12, fontSize: 12, fill: TICK }}
        />
        {/* One visible, titled axis (load). The level line rides a separate
            0-width scale so it never flattens into the load ruler; its own
            numerals mark the level. NEVER use `hide` on that second axis:
            recharts 3.10's axis-width pipeline breaks on hidden axes when the
            chart mounts synchronously (modal, demo), collapsing THIS axis's
            gutter and throwing its tick labels off-canvas. */}
        <YAxis
          yAxisId="load"
          axisLine={{ stroke: AXIS }}
          tickLine={{ stroke: AXIS }}
          width={56}
          domain={[0, (dataMax) => Math.max(Math.ceil(dataMax * 1.15), 1)]}
          allowDecimals={false}
          tick={{ fontSize: 12, fill: TICK }}
          label={{
            value: 'Cognitive load',
            angle: -90,
            position: 'insideLeft',
            offset: 4,
            fontSize: 12,
            fill: TICK,
            style: { textAnchor: 'middle' },
          }}
        />
        <YAxis
          yAxisId="level"
          width={0}
          tick={false}
          axisLine={false}
          tickLine={false}
          domain={[0.5, report.level_max + 0.5]}
        />
        {/* Entry animation only in the expand modal (big): there the layout is
            stable and the grow/draw reveal plays reliably, house-style. On the
            report's first mount the same animation races the container measure
            and can leave bars unpainted, so inline renders static. */}
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
          {/* No per-bar value labels (the original sketch has none): the axis
              gives the scale and the task table below holds exact values. */}
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
          {/* Sketch-density labelling: a numeral only where the level CHANGES,
              so a held run reads as one quiet number instead of a row of
              repeats. White halo keeps it legible over a bar. */}
          <LabelList dataKey="level" content={levelChangeLabel} />
        </Line>
      </ComposedChart>
    </ResponsiveContainer>
  );

  // One caption line instead of a legend row (the sketch has neither); the
  // axes name themselves now, so only the line and the flag need words.
  const chartSub = `Line: difficulty level.${
    anyFlag ? ' Amber bar: flagged, wrong without effort.' : ''
  }`;

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
                    <td data-label="Task">
                      <span className="rp-response">
                        {KIND_COPY[t.kind] || t.task_id}
                        <span className="rp-taskid">{taskItem(t.task_id)}</span>
                      </span>
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
      <p className="rp-disclaimer kr-reveal kr-reveal--4">{DISCLAIMER}</p>

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
            <p className="rp-disclaimer">{DISCLAIMER}</p>
          </div>
        </div>
      )}
    </div>
  );
}
