import { Badge, Tooltip } from '@patternfly/react-core';
import { SEV_CSS_VAR, SEVERITY_ORDER, SEVERITY_LABELS } from './severity';

interface SeverityStatusBarProps {
  sevCounts: Map<string, number>;
}

export function SeverityStatusBar({ sevCounts }: SeverityStatusBarProps) {
  const total = Array.from(sevCounts.values()).reduce((a, b) => a + b, 0);

  if (total === 0) {
    return (
      <div className="apme-severity-bar-wrapper">
        <Tooltip content="No violations found">
          <div className="apme-severity-bar-segment" style={{ flexGrow: 1 }} />
        </Tooltip>
      </div>
    );
  }

  return (
    <>
      <div className="apme-severity-bar-wrapper">
        {SEVERITY_ORDER.map((sev) => {
          const count = sevCounts.get(sev) ?? 0;
          if (count === 0) return null;
          return (
            <Tooltip
              key={sev}
              content={
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  {SEVERITY_LABELS[sev]} <Badge isRead>{count}</Badge>
                </span>
              }
            >
              <div
                className="apme-severity-bar-segment"
                style={{ flexGrow: count, backgroundColor: SEV_CSS_VAR[sev] }}
              />
            </Tooltip>
          );
        })}
      </div>
      <div className="apme-severity-bar-legend">
        {SEVERITY_ORDER.map((sev) => {
          const count = sevCounts.get(sev) ?? 0;
          if (count === 0) return null;
          const pct = Math.round((count / total) * 100);
          return (
            <div key={sev} className="apme-severity-bar-legend-item">
              <span className="apme-severity-bar-legend-box" style={{ backgroundColor: SEV_CSS_VAR[sev] }} />
              {SEVERITY_LABELS[sev]} {pct}%
            </div>
          );
        })}
      </div>
    </>
  );
}
