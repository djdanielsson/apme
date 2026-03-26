import { useState } from 'react';
import {
  Modal,
  ModalHeader,
  ModalBody,
  Tab,
  Tabs,
  TabTitleText,
} from '@patternfly/react-core';
import { PageDetails, PageDetail } from '@ansible/ansible-ui-framework';
import { severityClass, severityLabel, bareRuleId, ruleSource } from './severity';

function tierLabel(rc: number): string {
  if (rc === 1) return 'Fixable';
  if (rc === 2) return 'AI';
  if (rc === 3) return 'Manual';
  return 'Unknown';
}

export interface ViolationRecord {
  id: number;
  rule_id: string;
  level: string;
  message: string;
  file: string;
  line: number | null;
  path: string;
  remediation_class: number;
}

interface ViolationDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  violation: ViolationRecord;
  diff?: string;
  getRuleDescription?: (ruleId: string) => string | undefined;
  mergedViolations?: ViolationRecord[];
}

export function ViolationDetailModal({ isOpen, onClose, violation, diff, getRuleDescription, mergedViolations }: ViolationDetailModalProps) {
  const [activeTab, setActiveTab] = useState(0);
  const ruleDesc = getRuleDescription?.(violation.rule_id);
  const cls = severityClass(violation.level, violation.rule_id);
  const source = ruleSource(violation.rule_id);
  const isCombinedFixed = !!mergedViolations;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      aria-label="Violation details"
      width="75%"
    >
      <ModalHeader title={isCombinedFixed ? 'Fixed Violations' : 'Violation Details'} />
      <ModalBody>
        <Tabs
          aria-label="Violation detail tabs"
          activeKey={activeTab}
          onSelect={(_e, key) => setActiveTab(key as number)}
        >
          <Tab eventKey={0} title={<TabTitleText>Details</TabTitleText>} aria-label="Details tab">
            {isCombinedFixed ? (
              <div style={{ paddingTop: 12 }}>
                <p style={{ marginBottom: 12, opacity: 0.8 }}>
                  {mergedViolations.length} violation{mergedViolations.length !== 1 ? 's' : ''} fixed in <strong>{violation.file}</strong>
                </p>
                <table className="pf-v6-c-table pf-m-compact" role="grid">
                  <thead>
                    <tr role="row">
                      <th role="columnheader">Rule</th>
                      <th role="columnheader">Severity</th>
                      <th role="columnheader">Line</th>
                      <th role="columnheader">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mergedViolations.map((v) => (
                      <tr key={v.id} role="row">
                        <td role="cell"><span className="apme-rule-id">{bareRuleId(v.rule_id)}</span></td>
                        <td role="cell">
                          <span className={`apme-severity ${severityClass(v.level, v.rule_id)}`}>
                            {severityLabel(v.level, v.rule_id)}
                          </span>
                        </td>
                        <td role="cell">{v.line ?? ''}</td>
                        <td role="cell">{v.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <PageDetails>
                <PageDetail label="Rule">
                  <span className="apme-rule-id">{bareRuleId(violation.rule_id)}</span>
                </PageDetail>
                {source && (
                  <PageDetail label="Source">
                    {source}
                  </PageDetail>
                )}
                <PageDetail label="Severity">
                  <span className={`apme-severity ${cls}`}>
                    {severityLabel(violation.level, violation.rule_id)}
                  </span>
                </PageDetail>
                <PageDetail label="File">
                  {violation.file || '(unknown)'}
                </PageDetail>
                <PageDetail isEmpty={violation.line == null} label="Line">
                  {violation.line}
                </PageDetail>
                <PageDetail label="Remediation">
                  {tierLabel(violation.remediation_class)}
                </PageDetail>
                <PageDetail label="Message">
                  {violation.message}
                </PageDetail>
                {violation.path && (
                  <PageDetail label="YAML Path">
                    <code style={{ fontSize: 12 }}>{violation.path}</code>
                  </PageDetail>
                )}
                {ruleDesc && (
                  <PageDetail label="Rule Description">
                    {ruleDesc}
                  </PageDetail>
                )}
              </PageDetails>
            )}
          </Tab>
          {diff ? (
            <Tab eventKey={1} title={<TabTitleText>Diff</TabTitleText>} aria-label="Diff tab">
              <div className="apme-modal-diff">
                <pre>{diff}</pre>
              </div>
            </Tab>
          ) : null}
          <Tab eventKey={diff ? 2 : 1} title={<TabTitleText>Data</TabTitleText>} aria-label="Data tab">
            <div className="apme-modal-diff">
              <pre>{JSON.stringify(isCombinedFixed ? mergedViolations : violation, null, 2)}</pre>
            </div>
          </Tab>
        </Tabs>
      </ModalBody>
    </Modal>
  );
}
