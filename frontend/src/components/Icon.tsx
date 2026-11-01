import type { CSSProperties } from "react";

const paths: Record<string, string> = {
  dashboard: "M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 13h7v8H3z",
  pixel: "M4 4h6v6H4zM14 4h6v6h-6zM9 9h6v6H9zM4 14h6v6H4zM14 14h6v6h-6z",
  sprites: "M4 4h16v16H4zM4 9h16M4 15h16M9 4v16M15 4v16",
  tileset: "M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z",
  procedural: "M12 3l2.6 5.6L21 9.4l-4.5 4.3 1.1 6.3L12 17l-5.6 3 1.1-6.3L3 9.4l6.4-.8z",
  three_d: "M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 3v18M4 7.5l8 4.5 8-4.5",
  animation: "M4 5h16v14H4zM7 9l4 3-4 3zM15 9h2M15 12h2M15 15h2",
  library: "M4 4h5v16H4zM11 4h4v16h-4zM17 5l3 14",
  projects: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z",
  settings:
    "M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-2.9 1.2V21a2 2 0 11-4 0v-.1A1.7 1.7 0 006.9 19l-.1.1A2 2 0 114 16.3l.1-.1a1.7 1.7 0 00-1.2-2.9H2.8a2 2 0 110-4H3a1.7 1.7 0 001.2-2.9L4 6.3A2 2 0 116.9 3.5l.1.1A1.7 1.7 0 009.9 2.4V2.3a2 2 0 114 0v.1A1.7 1.7 0 0016.8 4l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 001.2 2.9h.1a2 2 0 110 4h-.1a1.7 1.7 0 00-1.4 1.3z",
  upload: "M12 16V4m0 0L7 9m5-5l5 5M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2",
  download: "M12 4v12m0 0l5-5m-5 5l-5-5M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2",
  plus: "M12 5v14M5 12h14",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6",
  refresh: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
  play: "M7 4l13 8-13 8z",
  pause: "M7 4h4v16H7zM13 4h4v16h-4z",
  chevron: "M9 6l6 6-6 6",
  close: "M6 6l12 12M18 6L6 18",
  check: "M4 12l5 5L20 6",
  zoomIn: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3M11 8v6M8 11h6",
  zoomOut: "M11 19a8 8 0 100-16 8 8 0 000 16zM21 21l-4.3-4.3M8 11h6",
  fit: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  grid: "M3 9h18M3 15h18M9 3v18M15 3v18",
  layers: "M12 3l9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5",
  eye: "M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
  eyeOff: "M3 3l18 18M10.6 10.6A3 3 0 0012 15a3 3 0 002.4-1.2M6.7 6.7C3.8 8.5 2 12 2 12s3.5 6 10 6c1.9 0 3.6-.5 5-1.3M17.9 15.4C20 13.7 22 12 22 12s-3.5-6-10-6c-.7 0-1.4.1-2 .2",
  save: "M5 3h11l4 4v14H5zM8 3v6h7V3M8 21v-7h8v7",
  folder: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2z",
  copy: "M8 8h12v12H8zM4 16V4h12",
  star: "M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z",
  spark: "M12 2v4M12 18v4M2 12h4M18 12h4M5 5l2.5 2.5M16.5 16.5L19 19M19 5l-2.5 2.5M7.5 16.5L5 19",
  info: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 10v6M12 7.5v.5",
};

export function Icon({
  name,
  size = 16,
  className = "",
  style,
  strokeWidth = 1.6,
}: {
  name: keyof typeof paths | string;
  size?: number;
  className?: string;
  style?: CSSProperties;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      <path d={paths[name] || paths.info} />
    </svg>
  );
}
