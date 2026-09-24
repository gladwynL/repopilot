import type { SVGProps } from 'react';

// Small inline icon set (16px grid, stroke-based) so the UI has no icon-font dependency.
const PATHS = {
  github:
    'M8 1.5a6.5 6.5 0 0 0-2.06 12.67c.33.06.44-.14.44-.31v-1.1c-1.8.39-2.18-.87-2.18-.87-.3-.75-.72-.95-.72-.95-.59-.4.04-.39.04-.39.65.05 1 .67 1 .67.58 1 1.52.71 1.9.54.05-.42.22-.71.4-.87-1.44-.16-2.95-.72-2.95-3.2 0-.71.25-1.29.67-1.74-.07-.17-.29-.83.06-1.72 0 0 .55-.18 1.79.66a6.2 6.2 0 0 1 3.26 0c1.24-.84 1.79-.66 1.79-.66.35.89.13 1.55.06 1.72.42.45.67 1.03.67 1.74 0 2.49-1.51 3.04-2.96 3.2.23.2.44.6.44 1.2v1.78c0 .17.11.37.45.31A6.5 6.5 0 0 0 8 1.5Z',
  external:
    'M9.5 2.5h4v4M13.5 2.5 7.5 8.5M11.5 9.5v3.5a.5.5 0 0 1-.5.5H3a.5.5 0 0 1-.5-.5V5a.5.5 0 0 1 .5-.5h3.5',
  file: 'M4 1.5h5l3.5 3.5v9a.5.5 0 0 1-.5.5H4a.5.5 0 0 1-.5-.5V2a.5.5 0 0 1 .5-.5ZM9 1.5V5h3.5',
  refresh: 'M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2v3h-3',
  arrowLeft: 'M13 8H3M7 4 3 8l4 4',
  history: 'M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v3h3M8 5v3.2l2 1.3',
  search: 'M7 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM10.7 10.7 14 14',
  beaker:
    'M6 1.5h4M6.5 1.5v4.2L2.9 12.3a1 1 0 0 0 .9 1.5h8.4a1 1 0 0 0 .9-1.5L9.5 5.7V1.5M4.5 9.5h7',
  info: 'M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM8 7.5V11M8 5h.01',
  alert: 'M8 1.8 1.5 13.5h13L8 1.8ZM8 6.5v3M8 11.5h.01',
  check: 'M3 8.5 6.5 12 13 4.5',
  cache:
    'M8 1.5c3.3 0 5.5 1 5.5 2.25S11.3 6 8 6 2.5 5 2.5 3.75 4.7 1.5 8 1.5ZM2.5 3.75v8.5C2.5 13.5 4.7 14.5 8 14.5s5.5-1 5.5-2.25v-8.5M2.5 8c0 1.25 2.2 2.25 5.5 2.25S13.5 9.25 13.5 8',
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 16, ...rest }: IconProps) {
  const filled = name === 'github';
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill={filled ? 'currentColor' : 'none'}
      stroke={filled ? 'none' : 'currentColor'}
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
