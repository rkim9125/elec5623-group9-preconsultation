import React from "react";
const paths = {
  // Patient-facing topic illustrations use recognisable anatomy or care objects.
  leg: (
    <path d="M8 2.5 7.5 8l2 5-1 6c-.1 1.2.6 2 1.8 2H17c1.1 0 1.5-1.2.5-1.8L14 17l.8-5-1.3-5 .5-4.5M8.8 11.3l4.5-.8" />
  ),
  backPain: (
    <>
      <path d="M8 3.5 7 6 3 8l2 5 2-1v8.5h10V12l2 1 2-5-4-2-1-2.5M12 5v10" />
      <path d="M10 7h4m-4 3h4m-4 3h4" />
      <circle cx="12" cy="18" r="2" />
    </>
  ),
  neckShoulder: (
    <>
      <path d="M9 3v5L4 10l-2 5 5 2v4m8-18v5l5 2 2 5-5 2v4M7 17v-4m10 4v-4" />
      <path d="m9 8 3 3 3-3M12 11v6" />
      <circle cx="17.5" cy="10.5" r="2.5" />
    </>
  ),
  handArm: (
    <path d="m8 21-4-7c-.8-1.4 1.2-2.5 2.1-1.3L8 15V5.5a1.3 1.3 0 0 1 2.6 0V11 3.5a1.3 1.3 0 0 1 2.6 0V11 5a1.3 1.3 0 0 1 2.6 0v6-3a1.3 1.3 0 0 1 2.6 0v8l-1.5 5M8 18h8.7" />
  ),
  headache: (
    <>
      <path d="M9 21v-3l-3-1v-4H4l2-3V9a7 7 0 0 1 14 0c0 3-1.5 4-2.5 6v6" />
      <path d="m12 5-2 4h3l-1 4M16 5h1m0 4h1" />
    </>
  ),
  dizziness: (
    <>
      <path d="M8 21v-4l-2-1v-4H4l2-3a7 7 0 0 1 13-2m-1 14v-4" />
      <path d="M20 10c-3-4-10-2-9 2 1 3 7 3 8 0 .7-2-2-3-3-1" />
      <path d="m18 7 2 3 2-3" />
    </>
  ),
  fatigue: (
    <>
      <rect x="3" y="5" width="17" height="14" rx="3" />
      <path d="M20 10h2v4h-2M7 9v6M11 10l2 2-2 2" />
    </>
  ),
  sleep: (
    <>
      <path d="M16 3a8 8 0 1 0 5 13A9 9 0 0 1 16 3Z" />
      <path d="M3 3h4L3 7h4m13-6v4m-2-2h4" />
    </>
  ),
  cough: (
    <>
      <path d="M6 21v-4l-2-1v-4H2l2-3a6.5 6.5 0 0 1 13 0v3m-2 9v-4M14 12h2" />
      <path d="m18 11 3-2m-3 5h4m-4 3 3 2" />
    </>
  ),
  nose: (
    <>
      <path d="M10 3 8 13c-4 2-2 6 1 5 2 2 4 2 6 0 3 1 5-3 1-5L14 3" />
      <path d="M8 16h1m6 0h1M3 6v4m-2-2h4m15 11v3m-1.5-1.5h3" />
    </>
  ),
  throat: (
    <>
      <path d="M8 3v5c0 2-4 3-5 4l-1 8h20l-1-8c-1-1-5-2-5-4V3M8 8c2 2 6 2 8 0M8 13l-3 2m11-2 3 2" />
      <rect x="10" y="11" width="4" height="7" rx="2" />
    </>
  ),
  ear: (
    <>
      <path d="M5 9a7 7 0 0 1 14 0c0 4-4 4-5 7s-2 5-5 5c-2 0-3-1-3-3M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4v2H9" />
      <path d="M2 8v4m20-4v4" />
    </>
  ),
  eye: (
    <>
      <path d="M2 11s4-6 10-6 10 6 10 6-4 6-10 6S2 11 2 11Z" />
      <circle cx="12" cy="11" r="3" />
      <path d="M19 17s-2 2.5-2 3.5a2 2 0 0 0 4 0c0-1-2-3.5-2-3.5Z" />
    </>
  ),
  abdomen: (
    <>
      <path d="M7 2c1 4 1 5-1 8s-2 6-1 12m12-20c-1 4-1 5 1 8s2 6 1 12M8 21h8" />
      <ellipse cx="12" cy="14" rx="4.5" ry="5" />
      <path d="M12 11v6m-2-3h4" />
    </>
  ),
  reflux: (
    <>
      <path d="M11 2v7c1 1 2 1 3 0 2-2 6 0 6 4 0 5-4 8-8 8s-8-3-8-6c0-2 2-3 4-1 2 1 3 0 3-2M14 2v5" />
      <path d="m6 9 2-2 2 2M8 7v5" />
    </>
  ),
  bowel: (
    <>
      <path d="M7 20c-3 0-4-2-4-5V8c0-3 2-4 4-3 1-2 4-2 5 0 2-2 5-1 5 1 3-1 4 1 4 3v6c0 3-2 4-5 4h-4v3M7 8v7h4m6-6v5H9m3-9v3" />
    </>
  ),
  looseStools: (
    <>
      <path d="M8 3C6 7 3 10 3 13a5 5 0 0 0 10 0c0-3-3-6-5-10ZM5.5 13c0 1.5 1 2.5 2.5 2.5" />
      <path d="M17 6h5m-5 5h5m-5 5h5m-5 5h5" />
    </>
  ),
  bladder: (
    <>
      <path d="M7 2v5m10-5v5M7 7c-4 0-5 3-4 6 1 4 5 6 9 6s8-2 9-6c1-3 0-6-4-6-2 0-3 2-5 2S9 7 7 7ZM12 19v3" />
      <path d="M9 13c1 1 5 1 6 0" />
    </>
  ),
  period: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M7 3v4m10-4v4M3 10h18M12 12s-3 3.5-3 5a3 3 0 0 0 6 0c0-1.5-3-5-3-5Z" />
    </>
  ),
  skin: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="6" />
      <path d="M3 13c3-3 5 3 9 0s5 3 9 0M7 17h1m4 1h1m4-2h1" />
      <circle cx="9" cy="8" r="1" />
      <circle cx="15" cy="7" r="1.5" />
    </>
  ),
  skinCare: (
    <>
      <path d="M7 3h10l-1 15H8L7 3ZM8 7h8M9 18v3h6v-3" />
      <path d="M11 10v4m-2-2h4M20 8v4m-2-2h4" />
    </>
  ),
  stress: (
    <>
      <path d="M8 21v-4l-2-1v-4H4l2-3a7 7 0 0 1 14 0c0 3-2 5-2 8v4" />
      <path d="M10 8c-2-2 3-4 4-2-4 1-2 5 1 3 2-2 3 2 1 3-2 1-6 0-5-2" />
    </>
  ),
  mood: (
    <>
      <path d="M21 11a9 9 0 0 1-9 9H5l-3 2v-6A9 9 0 1 1 21 11Z" />
      <path d="M8 9h.01M15 9h.01M8 14c2 1.5 5 1.5 7 0" />
    </>
  ),
  bloodPressure: (
    <>
      <rect x="3" y="5" width="12" height="15" rx="3" />
      <path d="M6 9h6M6 12h4M15 15h2c5 0 5-7 1-7M19 5v6" />
      <circle cx="9" cy="16.5" r="1" />
    </>
  ),
  diabetes: (
    <>
      <path d="M8 2C6 6 3 9 3 12a5 5 0 0 0 7 4.6" />
      <rect x="12" y="7" width="9" height="15" rx="2" />
      <path d="M15 10h3v5h-3zM15 18h3M5.5 12c0 1.5.9 2.5 2 2.5" />
    </>
  ),
  asthma: (
    <>
      <path d="M10 4v7c-2-4-4-6-6-2-1 2-3 9 0 11 2 1 4-1 6-3V11m4-7v7c2-4 4-6 6-2 1 2 3 9 0 11-2 1-4-1-6-3V11M10 7h4" />
    </>
  ),
  medicine: (
    <>
      <path d="m9 3 12 12a4.3 4.3 0 0 1-6 6L3 9a4.3 4.3 0 0 1 6-6ZM8 14l6-6" />
      <path d="m5 6 2-1" />
    </>
  ),
  results: (
    <>
      <path d="M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 16v2m4-5v5m4-7v7" />
    </>
  ),
  prevention: (
    <>
      <path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z" />
      <path d="M12 7v9m-4.5-4.5h9" />
    </>
  ),
  severalConcerns: (
    <>
      <rect x="3" y="3" width="8" height="8" rx="2" />
      <rect x="14" y="3" width="7" height="8" rx="2" />
      <rect x="3" y="14" width="8" height="7" rx="2" />
      <path d="M14 17h7m-3.5-3.5v7M5.5 7h3m-1.5-1.5v3" />
    </>
  ),
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  back: <path d="m14 6-6 6 6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  heart: (
    <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.9-8.6a5.5 5.5 0 0 0-.1-7.8Z" />
  ),
  activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  file: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21v-2a8 8 0 0 1 16 0v2" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  logout: (
    <>
      <path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  sparkle: (
    <>
      <path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3zM20 2v4M18 4h4" />
    </>
  ),
  upload: (
    <>
      <path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6" />
    </>
  ),
  mic: (
    <>
      <rect x="9" y="2" width="6" height="13" rx="3" />
      <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" />
    </>
  ),
  stop: <rect x="5" y="5" width="14" height="14" rx="2" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7h.01" />
    </>
  ),
  chevron: <path d="m9 5 7 7-7 7" />,
  download: (
    <>
      <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
    </>
  ),
  print: (
    <>
      <path d="M6 9V3h12v6M6 17H3V9h18v8h-3M6 14h12v7H6z" />
      <path d="M17 11h1" />
    </>
  ),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  trash: (
    <>
      <path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" />
    </>
  ),
};
export default function Icon({ name, size = 20, className = "" }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.file}
    </svg>
  );
}
