import { useMemo, useRef, useState } from 'react';
import { Button } from '@patternfly/react-core';
import {
  AngleDownIcon,
  AngleRightIcon,
  AngleDoubleUpIcon,
  AngleDoubleDownIcon,
} from '@patternfly/react-icons';
import { ViolationDetailModal, type ViolationRecord } from './ViolationDetailModal';
import { severityClass, severityLabel, severityOrder, scopeLabel } from './severity';
import { RuleId } from './RuleId';

import { RESOLUTION_AI_ABSTAINED } from '../types/constants';

function tierLabel(rc: number, isRemediate: boolean, resolution?: number): string {
  if (resolution === RESOLUTION_AI_ABSTAINED) return 'AI Tried';
  if (rc === 1) return isRemediate ? 'Fixed' : 'Fixable';
  if (rc === 2) return 'AI';
  if (rc === 3) return 'Manual';
  return '';
}

function tierPillClass(rc: number, isRemediate: boolean, resolution?: number): string {
  if (resolution === RESOLUTION_AI_ABSTAINED) return 'apme-pill apme-fix-ai-tried';
  if (rc === 1) return isRemediate ? 'apme-pill apme-fix-passed' : 'apme-pill apme-fix-fixable';
  if (rc === 2) return 'apme-pill apme-fix-ai';
  if (rc === 3) return 'apme-pill apme-fix-manual';
  return 'apme-pill';
}

function groupByFile(violations: ViolationRecord[]): Map<string, ViolationRecord[]> {
  const map = new Map<string, ViolationRecord[]>();
  for (const v of violations) {
    const key = v.file || '(unknown)';
    const arr = map.get(key) ?? [];
    arr.push(v);
    map.set(key, arr);
  }
  return map;
}

interface DisplayRow {
  type: 'violation';
  violation: ViolationRecord;
}

interface ViolationOutputProps {
  violations: ViolationRecord[];
  hasFilters: boolean;
  scanType?: string;
  onSectionToggle?: (open: boolean) => void;
  scanId?: string;
  feedbackEnabled?: boolean;
}

export function ViolationOutput({ violations, hasFilters, scanType, onSectionToggle, scanId, feedbackEnabled }: ViolationOutputProps) {
  const isRemediate = scanType === 'fix' || scanType === 'remediate';
  const [sectionOpen, setSectionOpen] = useState(true);
  const toggleSection = (open: boolean) => {
    setSectionOpen(open);
    onSectionToggle?.(open);
  };
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [allCollapsed, setAllCollapsed] = useState(false);
  const [selectedViolation, setSelectedViolation] = useState<ViolationRecord | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const groups = useMemo(() => groupByFile(violations), [violations]);

  const toggleFile = (file: string) => {
    setCollapsed(prev => ({ ...prev, [file]: !prev[file] }));
  };

  const expandAll = () => {
    const next: Record<string, boolean> = {};
    for (const key of groups.keys()) next[key] = false;
    setCollapsed(next);
    setAllCollapsed(false);
  };

  const collapseAll = () => {
    const next: Record<string, boolean> = {};
    for (const key of groups.keys()) next[key] = true;
    setCollapsed(next);
    setAllCollapsed(true);
  };

  const toggleAll = () => {
    if (allCollapsed) expandAll(); else collapseAll();
  };

  const isCollapsed = (file: string) => collapsed[file] === true;

  const buildRows = (_groupKey: string, fileViolations: ViolationRecord[]): DisplayRow[] => {
    const sorted = [...fileViolations].sort(
      (a, b) => severityOrder(severityClass(a.level, a.rule_id)) - severityOrder(severityClass(b.level, b.rule_id))
    );
    return sorted.map(v => ({ type: 'violation', violation: v }));
  };

  return (
    <>
      <div className="apme-output-controls">
        <div className="apme-output-controls-left">
          <Button
            variant="plain"
            onClick={() => toggleSection(!sectionOpen)}
            aria-label={sectionOpen ? 'Hide results' : 'Show results'}
            icon={sectionOpen ? <AngleDownIcon /> : <AngleRightIcon />}
            size="sm"
          />
          <span
            style={{ fontSize: 13, fontWeight: 600, paddingLeft: 4, cursor: 'pointer' }}
            role="button"
            tabIndex={0}
            onClick={() => toggleSection(!sectionOpen)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleSection(!sectionOpen); }}
          >
            Results ({violations.length})
          </span>
        </div>
        {sectionOpen && (
          <div className="apme-output-controls-right">
            <Button
              variant="plain"
              onClick={toggleAll}
              aria-label={allCollapsed ? 'Expand all files' : 'Collapse all files'}
              icon={allCollapsed ? <AngleRightIcon /> : <AngleDownIcon />}
              size="sm"
            />
            <Button
              variant="plain"
              onClick={() => {
                scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              icon={<AngleDoubleUpIcon />}
              aria-label="Scroll to top"
              size="sm"
            />
            <Button
              variant="plain"
              onClick={() => {
                const el = scrollRef.current;
                if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
              }}
              icon={<AngleDoubleDownIcon />}
              aria-label="Scroll to bottom"
              size="sm"
            />
          </div>
        )}
      </div>

      {sectionOpen && <div className="apme-output-scroll" ref={scrollRef}>
        <div className="apme-output-grid">
          {groups.size === 0 ? (
            <div className="apme-output-empty">
              No violations{hasFilters ? ' matching filters' : ' found'}.
            </div>
          ) : (
            Array.from(groups.entries()).map(([file, fileViolations]) => {
              const fixable = fileViolations.filter(v => v.remediation_class === 1);
              const rows = buildRows(file, fileViolations);

              return (
                <div className="apme-output-file-group" key={file}>
                  <div
                    className="apme-output-row apme-output-row-header"
                    role="button"
                    tabIndex={0}
                    onClick={() => toggleFile(file)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleFile(file); }}
                  >
                    <span className="apme-output-gutter">
                      {isCollapsed(file) ? <AngleRightIcon /> : <AngleDownIcon />}
                    </span>
                    <span className="apme-output-content apme-output-file-line">
                      <span className="apme-output-file-path">{file}</span>
                      <span className="apme-output-file-meta">
                        {fileViolations.length} issue{fileViolations.length !== 1 ? 's' : ''}
                        {fixable.length > 0 && (
                          <span className={isRemediate ? 'apme-badge passed' : 'apme-badge fixable'} style={{ marginLeft: 8, fontSize: 10 }}>
                            {fixable.length} {isRemediate ? 'fixed' : 'fixable'}
                          </span>
                        )}
                      </span>
                    </span>
                  </div>

                  {isCollapsed(file) && (
                    <div className="apme-output-row apme-output-row-ellipsis">
                      <span className="apme-output-gutter" />
                      <span className="apme-output-content">...</span>
                    </div>
                  )}

                  {!isCollapsed(file) && rows.map((row) => {
                    const v = row.violation;
                    return (
                      <div
                        className="apme-output-row apme-output-row-item"
                        key={v.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedViolation(v)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedViolation(v); }}
                      >
                        <span className="apme-output-gutter apme-output-line-num">
                          {v.line != null ? v.line : ''}
                        </span>
                        <span className="apme-output-content apme-output-violation-line">
                          <span className={`apme-pill apme-severity ${severityClass(v.level, v.rule_id)}`}>
                            {severityLabel(v.level, v.rule_id)}
                          </span>
                          <span className="apme-pill apme-output-violation-scope" title={v.path || ''}>
                            {scopeLabel(v.scope) || '\u00A0'}
                          </span>
                          <span
                            className={tierPillClass(v.remediation_class, isRemediate, v.remediation_resolution)}
                            style={{ visibility: v.remediation_class > 0 || v.remediation_resolution === RESOLUTION_AI_ABSTAINED ? 'visible' : 'hidden', minWidth: 50 }}
                          >
                            {tierLabel(v.remediation_class, isRemediate, v.remediation_resolution) || '\u00A0'}
                          </span>
                          <RuleId ruleId={v.rule_id} className="apme-pill apme-rule-pill" />
                          <span className="apme-output-violation-msg">
                            {v.message}
                          </span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            })
          )}
        </div>
      </div>}

      {selectedViolation && (
        <ViolationDetailModal
          isOpen={!!selectedViolation}
          onClose={() => setSelectedViolation(null)}
          violation={selectedViolation}
          scanType={scanType}
          scanId={scanId}
          feedbackEnabled={feedbackEnabled}
        />
      )}
    </>
  );
}
