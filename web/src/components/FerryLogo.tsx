interface Props {
  size?: number;
  className?: string;
}

export function FerryLogo({ size = 28, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M6 20 L16 20 L26 20 L23 26 L9 26 Z"
        stroke="var(--bob-light)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M16 20 L16 6 L21 9 L16 12"
        stroke="var(--bob-light)"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <line x1="11" y1="20" x2="11" y2="14" stroke="var(--bob-light)" strokeWidth="1.4" />
    </svg>
  );
}
