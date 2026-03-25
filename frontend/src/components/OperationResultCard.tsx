import type { ReactNode } from 'react';
import {
  Button,
  Card,
  CardBody,
  Flex,
  FlexItem,
  Split,
  SplitItem,
} from '@patternfly/react-core';
import type { OperationResult } from '../types/operation';

export interface OperationResultCardProps {
  result: OperationResult;
  onDismiss?: () => void;
  actions?: ReactNode;
}

export function OperationResultCard({
  result,
  onDismiss,
  actions,
}: OperationResultCardProps) {
  return (
    <Card style={{ marginBottom: 16, borderLeft: '4px solid var(--pf-t--global--color--status--success--default)' }}>
      <CardBody style={{ textAlign: 'center', padding: 32 }}>
        <div style={{ fontSize: 48, color: 'var(--pf-t--global--color--status--success--default)' }}>&#10003;</div>
        <h2>Operation Complete</h2>
        <Split hasGutter style={{ justifyContent: 'center', margin: '16px 0' }}>
          <SplitItem>
            <div style={{ fontSize: 32, fontWeight: 700 }}>{result.total_violations}</div>
            <div style={{ opacity: 0.7 }}>Violations</div>
          </SplitItem>
          <SplitItem>
            <div style={{ fontSize: 32, fontWeight: 700, color: 'var(--pf-t--global--color--status--success--default)' }}>
              {result.auto_fixable}
            </div>
            <div style={{ opacity: 0.7 }}>Auto-fixable</div>
          </SplitItem>
          <SplitItem>
            <div style={{ fontSize: 32, fontWeight: 700, color: 'var(--pf-t--global--color--status--warning--default)' }}>
              {result.ai_candidate}
            </div>
            <div style={{ opacity: 0.7 }}>AI Candidates</div>
          </SplitItem>
          <SplitItem>
            <div style={{ fontSize: 32, fontWeight: 700, color: 'var(--pf-t--global--color--status--danger--default)' }}>
              {result.manual_review}
            </div>
            <div style={{ opacity: 0.7 }}>Manual</div>
          </SplitItem>
          {result.fixed_count != null && result.fixed_count > 0 && (
            <SplitItem>
              <div style={{ fontSize: 32, fontWeight: 700, color: 'var(--pf-t--global--color--status--success--default)' }}>
                {result.fixed_count}
              </div>
              <div style={{ opacity: 0.7 }}>Fixed</div>
            </SplitItem>
          )}
        </Split>
        <Flex justifyContent={{ default: 'justifyContentCenter' }} gap={{ default: 'gapSm' }}>
          {actions}
          {onDismiss && (
            <FlexItem>
              <Button variant="link" onClick={onDismiss}>Dismiss</Button>
            </FlexItem>
          )}
        </Flex>
      </CardBody>
    </Card>
  );
}
