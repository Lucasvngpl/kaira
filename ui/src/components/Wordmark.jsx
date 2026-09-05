// The KAIRA wordmark, recreated as paths from the brand slide (2026-09-05):
// thin geometric capitals, wide tracking, both A's crossbar-less. Drawn SVG
// rather than styled text so it renders identically everywhere with no font
// to load. Deep Slate is fixed on purpose - a wordmark is not themeable.
const SLATE = '#263238';

// The A's are outlines (filled polygons) because a sharp apex needs exact
// edges; K, I and R are plain 9-unit strokes on a 108-unit cap height.
const LAMBDA = 'M51 0 L102 108 L91.2 108 L51 22.5 L10.8 108 L0 108 Z';

export default function Wordmark() {
  return (
    <svg className="kr-wordmark" viewBox="0 0 554 108" role="img" aria-label="Kaira">
      <g stroke={SLATE} strokeWidth="9" fill="none">
        <path d="M8 0 V108" />
        <path d="M84 3 L10 58 L88 105" />
        <path d="M290 0 V108" />
        <path d="M330 0 V108" />
        <path d="M330 4 H366 A26 26 0 0 1 366 56 H330" />
        <path d="M368 56 L400 104" />
      </g>
      <g fill={SLATE}>
        <path d={LAMBDA} transform="translate(136 0)" />
        <path d={LAMBDA} transform="translate(448 0)" />
      </g>
    </svg>
  );
}
