import { useMemo, useState } from 'react';
import {
  Card,
  CardBody,
  ExpandableSection,
  Flex,
  FlexItem,
  Label,
  Badge,
} from '@patternfly/react-core';
import {
  AngleDownIcon,
  AngleRightIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  ShieldAltIcon,
  InfoCircleIcon,
} from '@patternfly/react-icons';
import { severityClass, severityLabel, SEVERITY_ORDER, SEV_CSS_VAR } from './severity';
import type { ViolationDetail } from '../types/api';

const SCOPE_COLLECTION = 7;

interface CollectionGroup {
  fqcn: string;
  version: string;
  findings: ViolationDetail[];
  sevCounts: Map<string, number>;
}

interface CveGroup {
  pkg: string;
  version: string;
  cveId: string;
  severity: string;
  message: string;
  fixVersions: string;
}

function SevIcon({ sev }: { sev: string }) {
  const color = SEV_CSS_VAR[sev] ?? 'var(--apme-sev-info)';
  if (sev === 'critical' || sev === 'error') return <ExclamationCircleIcon style={{ color }} />;
  if (sev === 'high') return <ExclamationTriangleIcon style={{ color }} />;
  if (sev === 'medium') return <ShieldAltIcon style={{ color }} />;
  return <InfoCircleIcon style={{ color }} />;
}

function SevBadge({ sev, count }: { sev: string; count: number }) {
  const color = SEV_CSS_VAR[sev] ?? 'var(--apme-sev-info)';
  return (
    <span style={{ marginRight: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <SevIcon sev={sev} />
      <span style={{ fontWeight: 600, color }}>{count}</span>
    </span>
  );
}

export function isDepHealthViolation(v: ViolationDetail): boolean {
  return v.scope === SCOPE_COLLECTION || v.validator_source === 'dep_audit';
}

interface DependencyHealthPanelProps {
  violations: ViolationDetail[];
}

function CollectionFindingsTable({ findings }: { findings: ViolationDetail[] }) {
  const sorted = useMemo(
    () => [...findings].sort((a, b) => {
      const sevA = (SEVERITY_ORDER as readonly string[]).indexOf(severityClass(a.level, a.rule_id));
      const sevB = (SEVERITY_ORDER as readonly string[]).indexOf(severityClass(b.level, b.rule_id));
      if (sevA !== sevB) return sevA - sevB;
      return a.rule_id.localeCompare(b.rule_id);
    }),
    [findings],
  );

  const byRule = useMemo(() => {
    const groups = new Map<string, { rule_id: string; severity: string; message: string; count: number; files: string[] }>();
    for (const v of sorted) {
      const key = `${v.rule_id}::${v.message}`;
      if (!groups.has(key)) {
        groups.set(key, {
          rule_id: v.rule_id,
          severity: severityClass(v.level, v.rule_id),
          message: v.message,
          count: 0,
          files: [],
        });
      }
      const g = groups.get(key)!;
      g.count += 1;
      if (v.file && g.files.length < 5 && !g.files.includes(v.file)) {
        g.files.push(v.file);
      }
    }
    return Array.from(groups.values()).sort((a, b) => {
      const sevA = (SEVERITY_ORDER as readonly string[]).indexOf(a.severity);
      const sevB = (SEVERITY_ORDER as readonly string[]).indexOf(b.severity);
      if (sevA !== sevB) return sevA - sevB;
      return b.count - a.count;
    });
  }, [sorted]);

  return (
    <table className="pf-v6-c-table pf-m-compact" role="grid" style={{ marginTop: 4, marginBottom: 12 }}>
      <thead>
        <tr role="row">
          <th role="columnheader" style={{ width: 80 }}>Rule</th>
          <th role="columnheader" style={{ width: 80 }}>Severity</th>
          <th role="columnheader">Message</th>
          <th role="columnheader" style={{ width: 60 }}>Count</th>
          <th role="columnheader">Example files</th>
        </tr>
      </thead>
      <tbody>
        {byRule.map((g) => (
          <tr key={`${g.rule_id}-${g.message}`} role="row">
            <td role="cell">
              <span style={{ fontFamily: 'var(--pf-t--global--font--family--mono)', fontWeight: 600 }}>
                {g.rule_id}
              </span>
            </td>
            <td role="cell">
              <Label
                color={g.severity === 'critical' || g.severity === 'error' ? 'red' : g.severity === 'high' ? 'orange' : g.severity === 'medium' ? 'yellow' : 'blue'}
                isCompact
              >
                {severityLabel(g.severity).toUpperCase()}
              </Label>
            </td>
            <td role="cell" style={{ fontSize: 13 }}>{g.message}</td>
            <td role="cell"><Badge isRead>{g.count}</Badge></td>
            <td role="cell" style={{ fontSize: 12, fontFamily: 'var(--pf-t--global--font--family--mono)', opacity: 0.7 }}>
              {g.files.join(', ')}{g.count > g.files.length ? `, +${g.count - g.files.length} more` : ''}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DependencyHealthPanel({ violations }: DependencyHealthPanelProps) {
  const depViolations = useMemo(
    () => violations.filter(isDepHealthViolation),
    [violations],
  );

  const collectionGroups = useMemo(() => {
    const groups = new Map<string, CollectionGroup>();
    for (const v of depViolations) {
      if (v.scope !== SCOPE_COLLECTION) continue;
      const fqcn = v.path || 'unknown';
      const key = fqcn;
      if (!groups.has(key)) {
        groups.set(key, { fqcn, version: '', findings: [], sevCounts: new Map() });
      }
      const g = groups.get(key)!;
      g.findings.push(v);
      const cls = severityClass(v.level, v.rule_id);
      g.sevCounts.set(cls, (g.sevCounts.get(cls) ?? 0) + 1);
    }
    return Array.from(groups.values()).sort((a, b) => b.findings.length - a.findings.length);
  }, [depViolations]);

  const cveEntries = useMemo(() => {
    const entries: CveGroup[] = [];
    for (const v of depViolations) {
      if (v.validator_source !== 'dep_audit') continue;
      entries.push({
        pkg: v.path || v.file || '',
        version: '',
        cveId: v.rule_id === 'R200' ? (v.message.match(/CVE-\d{4}-\d+/)?.[0] ?? v.rule_id) : v.rule_id,
        severity: severityClass(v.level, v.rule_id),
        message: v.message,
        fixVersions: '',
      });
    }
    return entries;
  }, [depViolations]);

  const [collOpen, setCollOpen] = useState(true);
  const [pyOpen, setPyOpen] = useState(true);
  const [expandedColls, setExpandedColls] = useState<Set<string>>(new Set());

  if (depViolations.length === 0) return null;

  const totalCollFindings = collectionGroups.reduce((s, g) => s + g.findings.length, 0);

  const toggleColl = (fqcn: string) => {
    setExpandedColls((prev) => {
      const next = new Set(prev);
      if (next.has(fqcn)) next.delete(fqcn);
      else next.add(fqcn);
      return next;
    });
  };

  return (
    <div style={{ padding: '0 24px 16px' }}>
      <h3 style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <ShieldAltIcon />
        Dependency Health
        <Badge isRead>{depViolations.length}</Badge>
      </h3>

      {collectionGroups.length > 0 && (
        <ExpandableSection
          toggleText={`Collection Health — ${totalCollFindings} finding${totalCollFindings !== 1 ? 's' : ''} in ${collectionGroups.length} collection${collectionGroups.length !== 1 ? 's' : ''}`}
          isExpanded={collOpen}
          onToggle={(_e, val) => setCollOpen(val)}
          style={{ marginBottom: 12 }}
        >
          <Card isPlain>
            <CardBody style={{ padding: '8px 0' }}>
              {collectionGroups.map((g) => {
                const isExpanded = expandedColls.has(g.fqcn);
                return (
                  <div key={g.fqcn} style={{ borderBottom: '1px solid var(--pf-t--global--border--color--default)' }}>
                    <div
                      onClick={() => toggleColl(g.fqcn)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleColl(g.fqcn); } }}
                      tabIndex={0}
                      role="button"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: '10px 8px',
                        cursor: 'pointer',
                        userSelect: 'none',
                      }}
                    >
                      {isExpanded ? <AngleDownIcon /> : <AngleRightIcon />}
                      <span style={{ fontFamily: 'var(--pf-t--global--font--family--mono)', fontWeight: 600, minWidth: 200 }}>
                        {g.fqcn}
                      </span>
                      {g.version && (
                        <Label isCompact style={{ marginLeft: 4 }}>{g.version}</Label>
                      )}
                      <Badge isRead>{g.findings.length}</Badge>
                      <Flex style={{ marginLeft: 'auto' }}>
                        {SEVERITY_ORDER.map((sev) => {
                          const count = g.sevCounts.get(sev);
                          if (!count) return null;
                          return (
                            <FlexItem key={sev}>
                              <SevBadge sev={sev} count={count} />
                            </FlexItem>
                          );
                        })}
                      </Flex>
                    </div>
                    {isExpanded && (
                      <div style={{ paddingLeft: 28, paddingBottom: 8 }}>
                        <CollectionFindingsTable findings={g.findings} />
                      </div>
                    )}
                  </div>
                );
              })}
            </CardBody>
          </Card>
        </ExpandableSection>
      )}

      {cveEntries.length > 0 && (
        <ExpandableSection
          toggleText={`Python Dependencies — ${cveEntries.length} CVE${cveEntries.length !== 1 ? 's' : ''}`}
          isExpanded={pyOpen}
          onToggle={(_e, val) => setPyOpen(val)}
        >
          <Card isPlain>
            <CardBody style={{ padding: '8px 0' }}>
              <table className="pf-v6-c-table pf-m-compact" role="grid">
                <thead>
                  <tr role="row">
                    <th role="columnheader" style={{ width: 90 }}>Severity</th>
                    <th role="columnheader" style={{ width: 160 }}>CVE</th>
                    <th role="columnheader">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {cveEntries.map((cve, i) => (
                    <tr key={`${cve.cveId}-${i}`} role="row">
                      <td role="cell">
                        <Label
                          color={cve.severity === 'critical' ? 'red' : cve.severity === 'high' ? 'orange' : cve.severity === 'medium' ? 'yellow' : 'blue'}
                          isCompact
                        >
                          {severityLabel(cve.severity).toUpperCase()}
                        </Label>
                      </td>
                      <td role="cell">
                        <span style={{ fontFamily: 'var(--pf-t--global--font--family--mono)', fontWeight: 600 }}>
                          {cve.cveId}
                        </span>
                      </td>
                      <td role="cell" style={{ fontSize: 13 }}>
                        {cve.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardBody>
          </Card>
        </ExpandableSection>
      )}
    </div>
  );
}
