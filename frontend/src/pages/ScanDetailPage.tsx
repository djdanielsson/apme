import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import {
  Button,
  Label,
  Split,
  SplitItem,
  ExpandableSection,
} from '@patternfly/react-core';
import { deleteScan, getScan } from '../services/api';
import type { ScanDetail, ViolationDetail } from '../types/api';
import { getRuleDescription } from '../data/ruleDescriptions';

function groupByFile(violations: ViolationDetail[]): Map<string, ViolationDetail[]> {
  const map = new Map<string, ViolationDetail[]>();
  for (const v of violations) {
    const key = v.file || '(unknown)';
    const arr = map.get(key) ?? [];
    arr.push(v);
    map.set(key, arr);
  }
  return map;
}

function severityClass(level: string, ruleId?: string): string {
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

function severityLabel(level: string, ruleId?: string): string {
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

function classToLabel(cls: string): string {
  const map: Record<string, string> = {
    critical: 'Critical', error: 'Error', 'very-high': 'Very High',
    high: 'High', medium: 'Medium', warning: 'Warning',
    low: 'Low', 'very-low': 'Very Low', hint: 'Hint',
  };
  return map[cls] ?? cls;
}

function severityOrder(cls: string): number {
  const order: Record<string, number> = {
    critical: 0, error: 1, 'very-high': 2, high: 3,
    medium: 4, warning: 5, low: 6, 'very-low': 7, hint: 8,
  };
  return order[cls] ?? 9;
}

function tierLabel(rc: number): string {
  if (rc === 1) return 'Auto-Fix';
  if (rc === 2) return 'AI';
  if (rc === 3) return 'Manual';
  return '';
}

const SEVERITY_ORDER = ['critical', 'error', 'very-high', 'high', 'medium', 'warning', 'low', 'very-low', 'hint'];

const SEV_CSS_VAR: Record<string, string> = {
  critical: 'var(--apme-sev-critical)', error: 'var(--apme-sev-error)',
  'very-high': 'var(--apme-sev-very-high)', high: 'var(--apme-sev-high)',
  medium: 'var(--apme-sev-medium)', warning: 'var(--apme-sev-warning)',
  low: 'var(--apme-sev-low)', 'very-low': 'var(--apme-sev-very-low)',
  hint: 'var(--apme-sev-hint)',
};

interface FilterPopoverProps {
  sevFilters: Set<string>;
  ruleFilters: Set<string>;
  sevCounts: Map<string, number>;
  uniqueRules: string[];
  onSevChange: (next: Set<string>) => void;
  onRuleChange: (next: Set<string>) => void;
}

function FilterPopover({ sevFilters, ruleFilters, sevCounts, uniqueRules, onSevChange, onRuleChange }: FilterPopoverProps) {
  const [draftSev, setDraftSev] = useState(new Set(sevFilters));
  const [draftRule, setDraftRule] = useState(new Set(ruleFilters));

  const toggleDraftSev = (cls: string) => {
    setDraftSev((prev) => {
      const n = new Set(prev);
      if (n.has(cls)) n.delete(cls); else n.add(cls);
      return n;
    });
  };

  const toggleDraftRule = (rule: string) => {
    setDraftRule((prev) => {
      const n = new Set(prev);
      if (n.has(rule)) n.delete(rule); else n.add(rule);
      return n;
    });
  };

  const apply = () => {
    onSevChange(draftSev);
    onRuleChange(draftRule);
  };

  const clearAll = () => {
    setDraftSev(new Set());
    setDraftRule(new Set());
    onSevChange(new Set());
    onRuleChange(new Set());
  };

  return (
    <div className="apme-filter-popover" onClick={(e) => e.stopPropagation()}>
      <div className="apme-filter-scroll">
        <h4>Severity</h4>
        {SEVERITY_ORDER.map((cls) => {
          const count = sevCounts.get(cls) ?? 0;
          if (count === 0) return null;
          return (
            <label key={cls} className="apme-filter-option">
              <input type="checkbox" checked={draftSev.has(cls)} onChange={() => toggleDraftSev(cls)} />
              <span className="apme-sev-dot" style={{ background: SEV_CSS_VAR[cls] }} />
              <span style={{ flex: 1 }}>{classToLabel(cls)}</span>
              <span style={{ opacity: 0.6, fontSize: 12 }}>{count}</span>
            </label>
          );
        })}

        {uniqueRules.length > 0 && (
          <>
            <h4 style={{ marginTop: 12 }}>Rule</h4>
            {uniqueRules.map((r) => (
              <label key={r} className="apme-filter-option" title={getRuleDescription(r) || r}>
                <input type="checkbox" checked={draftRule.has(r)} onChange={() => toggleDraftRule(r)} />
                <span style={{ fontFamily: 'var(--pf-t--global--font--family--mono)', fontSize: 12 }}>{r}</span>
              </label>
            ))}
          </>
        )}
      </div>

      <div className="apme-filter-actions">
        <Button variant="link" onClick={clearAll} size="sm">Clear</Button>
        <Button variant="primary" onClick={apply} size="sm">Apply</Button>
      </div>
    </div>
  );
}

export function ScanDetailPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const navigate = useNavigate();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [sevFilters, setSevFilters] = useState<Set<string>>(new Set());
  const [ruleFilters, setRuleFilters] = useState<Set<string>>(new Set());
  const [logsOpen, setLogsOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const filterRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scanId) return;
    setLoading(true);
    getScan(scanId)
      .then(setScan)
      .catch(() => setScan(null))
      .finally(() => setLoading(false));
  }, [scanId]);

  useEffect(() => {
    if (!filterOpen) return;
    const handler = (e: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) setFilterOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [filterOpen]);

  const sevCounts = useMemo(() => {
    if (!scan) return new Map<string, number>();
    const counts = new Map<string, number>();
    for (const v of scan.violations) {
      const cls = severityClass(v.level, v.rule_id);
      counts.set(cls, (counts.get(cls) ?? 0) + 1);
    }
    return counts;
  }, [scan]);

  const uniqueRules = useMemo(() => {
    if (!scan) return [] as string[];
    const set = new Set<string>();
    for (const v of scan.violations) set.add(v.rule_id);
    return Array.from(set).sort();
  }, [scan]);

  const filtered = useMemo(() => {
    if (!scan) return [];
    let violations = scan.violations;
    if (sevFilters.size > 0) {
      violations = violations.filter((v) => sevFilters.has(severityClass(v.level, v.rule_id)));
    }
    if (ruleFilters.size > 0) {
      violations = violations.filter((v) => ruleFilters.has(v.rule_id));
    }
    return violations;
  }, [scan, sevFilters, ruleFilters]);

  const groups = useMemo(() => groupByFile(filtered), [filtered]);

  if (loading) return <PageLayout><div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div></PageLayout>;
  if (!scan) return <PageLayout><div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Scan not found.</div></PageLayout>;

  const expandAll = () => setExpanded(new Set(groups.keys()));
  const collapseAll = () => setExpanded(new Set());
  const hasFilters = sevFilters.size > 0 || ruleFilters.size > 0;
  const clearFilters = () => { setSevFilters(new Set()); setRuleFilters(new Set()); };
  const activeFilterCount = sevFilters.size + ruleFilters.size;

  const handleDelete = async () => {
    if (!scanId || !confirm('Delete this scan? This cannot be undone.')) return;
    try {
      await deleteScan(scanId);
      navigate('/scans');
    } catch {
      alert('Failed to delete scan.');
    }
  };

  return (
    <PageLayout>
      <PageHeader
        title={scan.project_path}
        breadcrumbs={[
          { label: 'Scans', to: '/scans' },
          { label: scan.project_path },
        ]}
        description={`${scan.scan_type} scan via ${scan.source} — ${new Date(scan.created_at).toLocaleString()}`}
        headerActions={
          <Button variant="danger" onClick={handleDelete} size="sm">
            Delete Scan
          </Button>
        }
      />

      <div style={{ padding: '0 24px 24px' }}>
        {/* Summary */}
        <Split hasGutter style={{ marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <SplitItem>
            <Label
              color={scan.total_violations > 0 ? 'red' : 'green'}
              isCompact={false}
            >
              {scan.total_violations > 0 ? `${scan.total_violations} VIOLATIONS` : 'CLEAN'}
            </Label>
          </SplitItem>
          {scan.violations.length > 0 && SEVERITY_ORDER.map((cls) => {
            const count = sevCounts.get(cls) ?? 0;
            if (count === 0) return null;
            return (
              <SplitItem key={cls}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                  <span className="apme-sev-dot" style={{ background: SEV_CSS_VAR[cls] }} />
                  <strong>{count}</strong>
                  <span style={{ opacity: 0.7 }}>{classToLabel(cls)}</span>
                </span>
              </SplitItem>
            );
          })}
          <SplitItem isFilled />
          <SplitItem>
            <Split hasGutter>
              {scan.scan_type === 'fix' && scan.fixed_count > 0 && (
                <SplitItem>
                  <strong style={{ color: 'var(--pf-t--global--color--status--success--default)' }}>{scan.fixed_count}</strong> Fixed
                </SplitItem>
              )}
              <SplitItem>
                <strong style={{ color: 'var(--pf-t--global--color--status--success--default)' }}>{scan.auto_fixable}</strong> Auto-Fix
              </SplitItem>
              <SplitItem>
                <strong style={{ color: 'var(--pf-t--global--color--status--warning--default)' }}>{scan.ai_candidate}</strong> AI
              </SplitItem>
              <SplitItem>
                <strong style={{ color: 'var(--pf-t--global--color--status--danger--default)' }}>{scan.manual_review}</strong> Manual
              </SplitItem>
            </Split>
          </SplitItem>
        </Split>

        {/* Filter bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div className="apme-filter-anchor" ref={filterRef}>
            <Button variant="secondary" onClick={() => setFilterOpen((p) => !p)} size="sm">
              Filter{activeFilterCount > 0 && ` (${activeFilterCount})`}
            </Button>
            {filterOpen && (
              <FilterPopover
                sevFilters={sevFilters}
                ruleFilters={ruleFilters}
                sevCounts={sevCounts}
                uniqueRules={uniqueRules}
                onSevChange={(s) => { setSevFilters(s); setFilterOpen(false); }}
                onRuleChange={(r) => { setRuleFilters(r); setFilterOpen(false); }}
              />
            )}
          </div>
          {hasFilters && (
            <>
              {Array.from(sevFilters).map((cls) => (
                <Label key={cls} onClose={() => setSevFilters((p) => { const n = new Set(p); n.delete(cls); return n; })} isCompact>
                  {classToLabel(cls)}
                </Label>
              ))}
              {Array.from(ruleFilters).map((r) => (
                <Label key={r} onClose={() => setRuleFilters((p) => { const n = new Set(p); n.delete(r); return n; })} isCompact variant="outline">
                  {r}
                </Label>
              ))}
              <Button variant="link" onClick={clearFilters} size="sm">Clear all</Button>
              <span style={{ opacity: 0.7, fontSize: 13 }}>
                {filtered.length} of {scan.violations.length}
              </span>
            </>
          )}
        </div>

        {/* Pipeline logs */}
        {scan.logs.length > 0 && (
          <ExpandableSection
            toggleText={`Pipeline Log (${scan.logs.length})`}
            isExpanded={logsOpen}
            onToggle={(_e, expanded) => setLogsOpen(expanded)}
            style={{ marginBottom: 24 }}
          >
            <table className="pf-v6-c-table pf-m-compact" role="grid">
              <thead>
                <tr role="row"><th role="columnheader">Phase</th><th role="columnheader">Message</th></tr>
              </thead>
              <tbody>
                {scan.logs.map((lg) => (
                  <tr key={lg.id} role="row">
                    <td role="cell"><Label isCompact>{lg.phase}</Label></td>
                    <td role="cell">{lg.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ExpandableSection>
        )}

        {/* Violations by file */}
        <div className="apme-violations-section">
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--pf-t--global--border--color--default)', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 600, marginRight: 'auto' }}>
              Violations by File ({filtered.length})
            </span>
            <Button variant="secondary" onClick={expandAll} size="sm">Expand All</Button>
            <Button variant="secondary" onClick={collapseAll} size="sm">Collapse All</Button>
          </div>

          {groups.size === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>
              No violations{hasFilters ? ' matching filters' : ' found'}.
            </div>
          ) : (
            Array.from(groups.entries()).map(([file, violations]) => (
              <div className="apme-file-group" key={file}>
                <div className="apme-file-header" onClick={() => {
                  setExpanded((prev) => {
                    const next = new Set(prev);
                    if (next.has(file)) next.delete(file);
                    else next.add(file);
                    return next;
                  });
                }}>
                  <span style={{ opacity: 0.5 }}>{expanded.has(file) ? '\u25BC' : '\u25B6'}</span>
                  <span className="apme-file-name">{file}</span>
                  <span className="apme-file-count">{violations.length} issues</span>
                </div>
                {expanded.has(file) &&
                  violations
                    .sort((a: ViolationDetail, b: ViolationDetail) =>
                      severityOrder(severityClass(a.level, a.rule_id)) - severityOrder(severityClass(b.level, b.rule_id)),
                    )
                    .map((v: ViolationDetail) => (
                    <div className="apme-violation-item" key={v.id}>
                      <span className={`apme-severity ${severityClass(v.level, v.rule_id)}`}>
                        {severityLabel(v.level, v.rule_id)}
                      </span>
                      <span className="apme-rule-id" title={getRuleDescription(v.rule_id) || v.rule_id}>{v.rule_id}</span>
                      <span className="apme-badge running" style={{ fontSize: 10, visibility: v.remediation_class > 0 ? 'visible' : 'hidden' }}>
                        {tierLabel(v.remediation_class) || '\u00A0'}
                      </span>
                      <span className="apme-line-number" style={{ visibility: v.line != null ? 'visible' : 'hidden' }}>
                        {v.line != null ? `Line ${v.line}` : '\u00A0'}
                      </span>
                      <div className="apme-violation-message">
                        {v.message}
                        {v.path && <span style={{ display: 'block', fontSize: 11, opacity: 0.5, fontFamily: 'var(--pf-t--global--font--family--mono)' }}>{v.path}</span>}
                      </div>
                    </div>
                  ))}
              </div>
            ))
          )}
        </div>

        {/* AI proposals */}
        {scan.proposals.length > 0 && (
          <div style={{ marginTop: 24 }}>
            <h3 style={{ marginBottom: 12 }}>AI Proposals ({scan.proposals.length})</h3>
            <table className="pf-v6-c-table pf-m-compact" role="grid">
              <thead>
                <tr role="row">
                  <th role="columnheader" style={{ width: 90 }}>Rule</th>
                  <th role="columnheader">File</th>
                  <th role="columnheader" style={{ width: 50 }}>Tier</th>
                  <th role="columnheader" style={{ width: 80 }}>Confidence</th>
                  <th role="columnheader" style={{ width: 80 }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {scan.proposals.map((p) => (
                  <tr key={p.id} role="row">
                    <td role="cell"><span className="apme-rule-id">{p.rule_id}</span></td>
                    <td role="cell" style={{ fontSize: 13 }}>{p.file}</td>
                    <td role="cell">{p.tier}</td>
                    <td role="cell">{Math.round(p.confidence * 100)}%</td>
                    <td role="cell">
                      <Label color={p.status === 'approved' ? 'green' : p.status === 'rejected' ? 'red' : 'blue'} isCompact>
                        {p.status}
                      </Label>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Diagnostics */}
        {scan.diagnostics_json && (
          <ExpandableSection toggleText="Diagnostics (raw)" style={{ marginTop: 24 }}>
            <pre style={{ padding: 16, fontSize: 12, overflow: 'auto', maxHeight: 400, background: 'var(--pf-t--global--background--color--secondary--default)' }}>
              {(() => {
                try { return JSON.stringify(JSON.parse(scan.diagnostics_json), null, 2); }
                catch { return scan.diagnostics_json; }
              })()}
            </pre>
          </ExpandableSection>
        )}
      </div>
    </PageLayout>
  );
}
