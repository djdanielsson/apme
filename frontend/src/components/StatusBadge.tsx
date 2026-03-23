interface StatusBadgeProps {
  violations: number;
  scanType: string;
}

export function StatusBadge({ violations, scanType }: StatusBadgeProps) {
  if (violations > 0) {
    return <span className="apme-badge failed">{"\u2717"} {violations} ISSUES</span>;
  }
  if (scanType === "fix") {
    return <span className="apme-badge passed">{"\u2713"} FIXED</span>;
  }
  return <span className="apme-badge passed">{"\u2713"} CLEAN</span>;
}
