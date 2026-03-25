import { useCallback, useState } from 'react';
import {
  Button,
  Card,
  CardBody,
  Flex,
  Label,
  Split,
  SplitItem,
} from '@patternfly/react-core';
import type { OperationProposal } from '../types/operation';

export interface ProposalReviewPanelProps {
  proposals: OperationProposal[];
  onApprove: (ids: string[]) => void;
}

export function ProposalReviewPanel({
  proposals,
  onApprove,
}: ProposalReviewPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  const toggleAll = useCallback(() => {
    setSelected((prev) =>
      prev.size === proposals.length
        ? new Set()
        : new Set(proposals.map((p) => p.id)),
    );
  }, [proposals]);

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const allSelected = selected.size === proposals.length;

  return (
    <Card style={{ marginBottom: 16 }}>
      <CardBody>
        <Split hasGutter style={{ marginBottom: 16 }}>
          <SplitItem isFilled>
            <Label color="yellow" isCompact>AI Review</Label>
            <h3 style={{ marginTop: 4 }}>
              {proposals.length} AI Proposal{proposals.length !== 1 ? 's' : ''}
            </h3>
          </SplitItem>
          <SplitItem>
            <Flex gap={{ default: 'gapSm' }}>
              <Button variant="secondary" onClick={toggleAll} size="sm">
                {allSelected ? 'Deselect All' : 'Select All'}
              </Button>
              <Button variant="link" onClick={() => onApprove([])} size="sm">Skip All</Button>
              <Button variant="primary" onClick={() => onApprove(Array.from(selected))} size="sm">
                Apply {selected.size} Selected
              </Button>
            </Flex>
          </SplitItem>
        </Split>
        <div className="apme-proposals-list" role="group" aria-label="AI fix proposals">
          {proposals.map((p) => (
            <div
              key={p.id}
              className={`apme-proposal-card ${selected.has(p.id) ? 'selected' : ''}`}
              role="checkbox"
              aria-checked={selected.has(p.id)}
              tabIndex={0}
              onClick={() => toggle(p.id)}
              onKeyDown={(e) => {
                if (e.key === ' ' || e.key === 'Enter') {
                  e.preventDefault();
                  toggle(p.id);
                }
              }}
            >
              <input type="checkbox" checked={selected.has(p.id)} readOnly tabIndex={-1} aria-hidden="true" className="apme-proposal-checkbox" />
              <span className="apme-rule-id">{p.rule_id}</span>
              <span className="apme-proposal-file">{p.file}</span>
              <Label isCompact variant="outline">Tier {p.tier}</Label>
              <span className="apme-confidence-label">{Math.round(p.confidence * 100)}%</span>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
