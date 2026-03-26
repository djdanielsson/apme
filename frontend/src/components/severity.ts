/**
 * Shared severity utilities — single source of truth for mapping API severity
 * levels to CSS classes, display labels, and color variables.
 *
 * All severity-related rendering should import from this module to avoid drift.
 */

export const SEV_CSS_VAR: Record<string, string> = {
  critical: 'var(--apme-sev-critical)',
  error: 'var(--apme-sev-error)',
  'very-high': 'var(--apme-sev-very-high)',
  high: 'var(--apme-sev-high)',
  medium: 'var(--apme-sev-medium)',
  warning: 'var(--apme-sev-warning)',
  low: 'var(--apme-sev-low)',
  'very-low': 'var(--apme-sev-very-low)',
  hint: 'var(--apme-sev-hint)',
};

export const SEVERITY_ORDER = [
  'critical', 'error', 'very-high', 'high', 'medium', 'warning', 'low', 'very-low', 'hint',
] as const;

export const SEVERITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  error: 'Error',
  'very-high': 'Very High',
  high: 'High',
  medium: 'Medium',
  warning: 'Warning',
  low: 'Low',
  'very-low': 'Very Low',
  hint: 'Hint',
};

const SEVERITY_RANK: Record<string, number> = {
  critical: 0, error: 1, 'very-high': 2, high: 3,
  medium: 4, warning: 5, low: 6, 'very-low': 7, hint: 8,
};

/**
 * Map an API-level severity string (and optional rule ID) to a CSS class slug.
 * SEC-prefixed rules always map to "critical".
 */
export function severityClass(level: string, ruleId?: string): string {
  if (ruleId?.startsWith('SEC')) return 'critical';
  const l = level.toLowerCase();
  if (l === 'fatal') return 'critical';
  if (l === 'error') return 'error';
  if (l === 'very_high') return 'very-high';
  if (l === 'high') return 'high';
  if (l === 'medium') return 'medium';
  if (['warning', 'warn'].includes(l)) return 'warning';
  if (l === 'low') return 'low';
  if (['very_low', 'info'].includes(l)) return 'very-low';
  return 'hint';
}

/** Upper-case display label for the severity badge text. */
export function severityLabel(level: string, ruleId?: string): string {
  if (ruleId?.startsWith('SEC')) return 'CRITICAL';
  const l = level.toLowerCase();
  if (l === 'fatal') return 'FATAL';
  if (l === 'error') return 'ERROR';
  if (l === 'very_high') return 'VERY HIGH';
  if (l === 'high') return 'HIGH';
  if (l === 'medium') return 'MEDIUM';
  if (['warning', 'warn'].includes(l)) return 'WARN';
  if (l === 'low') return 'LOW';
  if (['very_low', 'info'].includes(l)) return 'VERY LOW';
  return 'HINT';
}

/** Numeric sort weight — lower = more severe. */
export function severityOrder(cls: string): number {
  return SEVERITY_RANK[cls] ?? 9;
}

/**
 * Map a health score (0–100) to a CSS color string.
 * 0–24 red, 25–49 orange, 50–74 yellow/gold, 75–100 green.
 */
export function healthColor(score: number): string {
  if (score < 25) return 'var(--apme-sev-critical)';
  if (score < 50) return 'var(--apme-sev-high)';
  if (score < 75) return 'var(--apme-sev-medium)';
  return 'var(--apme-green)';
}

/**
 * Map a health score to a PF Label-compatible color name.
 * 0–24 red, 25–49 orange, 50–74 yellow, 75–100 green.
 */
export function healthLabelColor(score: number): 'red' | 'orange' | 'yellow' | 'green' {
  if (score < 25) return 'red';
  if (score < 50) return 'orange';
  if (score < 75) return 'yellow';
  return 'green';
}

/** Strip validator prefix from a rule ID (e.g. "native:L042" → "L042"). */
export function bareRuleId(ruleId: string): string {
  const idx = ruleId.indexOf(':');
  if (idx > 0 && idx < ruleId.length - 1) return ruleId.slice(idx + 1);
  return ruleId;
}

/** Extract the validator source from a rule ID (e.g. "native:L042" → "native"). */
export function ruleSource(ruleId: string): string | null {
  const idx = ruleId.indexOf(':');
  if (idx > 0) return ruleId.slice(0, idx);
  return null;
}
