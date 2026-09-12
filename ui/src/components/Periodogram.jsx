// The load formula, drawn live: frontal curve with theta shaded blue,
// parietal with alpha shaded green - load is ln(blue area / green area).
// Curves come from the server's PSD (same Welch settings as features.py).
// Hand-rolled SVG per house rule; no y-axis because the ratio is the story.
import '../styles/session.css';

const THETA = [4, 8];
const ALPHA = [8, 12];
const W = 260;
const H = 72;

export default function Periodogram({ spectrum, paused }) {
  const { freqs, frontal, parietal } = spectrum;
  if (!freqs?.length || !frontal?.length || !parietal?.length) return null;

  const f0 = freqs[0];
  const f1 = freqs[freqs.length - 1];
  const x = (f) => ((f - f0) / (f1 - f0)) * W;
  const yMax = Math.max(...frontal, ...parietal) * 1.08 || 1;
  const y = (v) => H - 2 - (v / yMax) * (H - 8);
  const pct = (f) => `${(((f - f0) / (f1 - f0)) * 100).toFixed(1)}%`;

  const line = (vals) =>
    vals.map((v, i) => `${x(freqs[i]).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  // The shaded band: the curve between the band edges, closed down to the
  // x-axis - literally the power the formula integrates.
  const band = (vals, [a, b]) => {
    const inside = freqs
      .map((f, i) => [f, vals[i]])
      .filter(([f]) => f >= a && f <= b)
      .map(([f, v]) => `${x(f).toFixed(1)},${y(v).toFixed(1)}`);
    return [`${x(a).toFixed(1)},${H}`, ...inside, `${x(b).toFixed(1)},${H}`].join(' ');
  };

  return (
    <figure className={`sn-psd${paused ? ' sn-psd--paused' : ''}`}>
      <p className="sn-chartlabel">Live spectrum &middot; Welch PSD &middot; 2-20 Hz</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <polygon className="sn-psd__band sn-psd__band--theta" points={band(frontal, THETA)} />
        <polygon className="sn-psd__band sn-psd__band--alpha" points={band(parietal, ALPHA)} />
        <polyline className="sn-psd__line sn-psd__line--frontal" points={line(frontal)} vectorEffect="non-scaling-stroke" />
        <polyline className="sn-psd__line sn-psd__line--parietal" points={line(parietal)} vectorEffect="non-scaling-stroke" />
      </svg>
      {/* Band letters + edge frequencies, positioned on the same scale the
          curves use, so labels and shading can never drift apart. */}
      <div className="sn-psd__axis" aria-hidden="true">
        <span className="sn-psd__glyph sn-psd__glyph--theta" style={{ left: pct(6) }}>&theta;</span>
        <span className="sn-psd__glyph sn-psd__glyph--alpha" style={{ left: pct(10) }}>&alpha;</span>
        {[4, 8, 12].map((f) => (
          <span key={f} className="sn-psd__tick" style={{ left: pct(f) }}>
            {f}
          </span>
        ))}
        <span className="sn-psd__tick sn-psd__tick--unit">Hz</span>
      </div>
      <figcaption className="sn-psd__legend">
        <span>
          <i className="sn-psd__dot sn-psd__dot--frontal" /> Frontal F3&middot;Fz&middot;F4
        </span>
        <span>
          <i className="sn-psd__dot sn-psd__dot--parietal" /> Parietal P3&middot;Pz&middot;P4
        </span>
      </figcaption>
      <p className="sn-psd__formula">load = ln(frontal &theta; power / parietal &alpha; power)</p>
    </figure>
  );
}
