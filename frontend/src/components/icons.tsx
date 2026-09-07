/**
 * Icon set — inline SVG, single stroke weight, sized from the surrounding text.
 *
 * Hand-drawn on a 24px grid rather than pulled from an icon package: it keeps the bundle
 * free of another dependency and lets every glyph share the geometric, faceted feel of
 * the rest of the interface.
 */

type IconProps = {
  className?: string;
  size?: number;
};

function Svg({
  children,
  className = "",
  size = 18,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

export function IconDashboard(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="3" width="7.5" height="8.5" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
      <rect x="3" y="14.5" width="7.5" height="6.5" rx="1.5" />
      <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
    </Svg>
  );
}

export function IconExam(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v5h5" />
      <path d="M9 13l1.8 1.8L14.5 11" />
      <path d="M9 18h6" />
    </Svg>
  );
}

export function IconResults(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-7" />
      <path d="M2 20h20" />
    </Svg>
  );
}

export function IconPerformance(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 17.5 9 11l4 4 8-8.5" />
      <path d="M15.5 6.5H21V12" />
    </Svg>
  );
}

export function IconProfile(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="8.5" r="3.75" />
      <path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" />
    </Svg>
  );
}

export function IconSettings(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.5v2.2M12 19.3v2.2M21.5 12h-2.2M4.7 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9 5.3 5.3" />
    </Svg>
  );
}

export function IconSignOut(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15" />
      <path d="M10 16l-4-4 4-4" />
      <path d="M6 12h10" />
    </Svg>
  );
}

export function IconUsers(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="3.25" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <path d="M16.5 5.4a3.25 3.25 0 0 1 0 5.2" />
      <path d="M18 14.6A6 6 0 0 1 21 20" />
    </Svg>
  );
}

export function IconBank(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6.5c0-1.4 3.6-2.5 8-2.5s8 1.1 8 2.5-3.6 2.5-8 2.5-8-1.1-8-2.5Z" />
      <path d="M4 6.5v11c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-11" />
      <path d="M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5" />
    </Svg>
  );
}

export function IconGrading(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H15l5 5v9.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5Z" />
      <path d="M8 14.5l2.2 2.2L16 11" />
    </Svg>
  );
}

export function IconShield(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3l7.5 3v5.5c0 4.6-3.1 8.3-7.5 9.5-4.4-1.2-7.5-4.9-7.5-9.5V6Z" />
      <path d="M9.2 12.2 11.3 14.3 15 10.5" />
    </Svg>
  );
}

export function IconClock(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 1.8" />
    </Svg>
  );
}

export function IconCamera(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="13.5" r="3.5" />
    </Svg>
  );
}

export function IconCheck(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 12.5 9.5 17 19 7.5" />
    </Svg>
  );
}

export function IconAlert(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3.5 21.5 20h-19Z" />
      <path d="M12 10v4" />
      <path d="M12 17.2v.1" />
    </Svg>
  );
}

export function IconHourglass(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M7 3h10" />
      <path d="M7 21h10" />
      <path d="M7 3v3.5c0 2 5 3.9 5 5.5s-5 3.5-5 5.5V21" />
      <path d="M17 3v3.5c0 2-5 3.9-5 5.5s5 3.5 5 5.5V21" />
    </Svg>
  );
}

export function IconArrowRight(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 12h14" />
      <path d="M13 6l6 6-6 6" />
    </Svg>
  );
}

export function IconMonitor(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="12.5" rx="1.5" />
      <path d="M9 20h6" />
      <path d="M12 16.5V20" />
    </Svg>
  );
}

export function IconList(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
    </Svg>
  );
}
