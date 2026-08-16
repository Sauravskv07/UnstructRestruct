export default function NetworkBackdrop() {
  return (
    <div className="network-backdrop" aria-hidden="true">
      <svg className="network-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="lineGlow" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7eb6ff" stopOpacity="0" />
            <stop offset="50%" stopColor="#7eb6ff" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#7eb6ff" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g className="network-lines" fill="none" stroke="#4f8fd4" strokeWidth="1.2">
          <path d="M40 120 C 220 40, 380 220, 560 140 S 880 40, 1160 180" />
          <path d="M-20 320 C 180 240, 360 420, 540 300 S 900 220, 1220 380" />
          <path d="M60 520 C 260 440, 420 640, 640 540 S 940 460, 1180 620" />
          <path d="M80 700 C 300 620, 500 760, 720 680 S 1000 600, 1240 740" />
          <path d="M200 40 C 280 200, 240 380, 420 460 S 700 520, 780 720" />
          <path d="M980 60 C 860 180, 920 340, 780 430 S 560 510, 500 760" />
        </g>
        <g className="network-flow" fill="none" stroke="url(#lineGlow)" strokeWidth="2.2">
          <path d="M40 120 C 220 40, 380 220, 560 140 S 880 40, 1160 180" />
          <path d="M-20 320 C 180 240, 360 420, 540 300 S 900 220, 1220 380" />
          <path d="M60 520 C 260 440, 420 640, 640 540 S 940 460, 1180 620" />
        </g>
        <g className="network-nodes" fill="#9fd0ff">
          <circle cx="560" cy="140" r="3.5" />
          <circle cx="540" cy="300" r="3.5" />
          <circle cx="640" cy="540" r="3.5" />
          <circle cx="420" cy="460" r="3" />
          <circle cx="780" cy="430" r="3" />
          <circle cx="200" cy="40" r="2.5" />
          <circle cx="980" cy="60" r="2.5" />
          <circle cx="720" cy="680" r="3" />
        </g>
        <circle className="network-dot d1" r="4.5" fill="#d7ecff" />
        <circle className="network-dot d2" r="4" fill="#d7ecff" />
        <circle className="network-dot d3" r="3.5" fill="#d7ecff" />
      </svg>
    </div>
  );
}
