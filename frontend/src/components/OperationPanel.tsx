/**
 * OperationPanel — pure state-to-screen renderer for project operations (ADR-052).
 *
 * Renders the correct UI panel based on the current OperationState.status.
 * All 11 states map to a specific UI:
 *
 *   queued          → spinner + "Starting..."
 *   cloning         → progress bar + clone status
 *   scanning        → streaming progress log
 *   awaiting_approval → proposal review panel
 *   applying        → progress log + "Applying fixes..."
 *   completed       → results + violations + Create PR
 *   submitting_pr   → results + PR spinner
 *   pr_submitted    → results + PR link
 *   failed          → error banner
 *   expired         → "Session expired" banner
 *   cancelled       → null (no panel)
 */

import { useCallback, useState } from 'react';
import {
  Button,
  Card,
  CardBody,
  Flex,
  FlexItem,
  Spinner,
} from '@patternfly/react-core';
import type {
  ProjectOperationState,
  ProjectOperationStatus,
} from '../hooks/useProjectOperationState';
import type { OperationProgress, OperationResult } from '../types/operation';
import { OperationProgressPanel } from './OperationProgressPanel';
import { ProposalReviewPanel } from './ProposalReviewPanel';
import { OperationResultCard } from './OperationResultCard';

export interface OperationPanelProps {
  state: ProjectOperationState | null;
  onApprove: (ids: string[]) => Promise<unknown>;
  onCancel: () => Promise<unknown>;
  onCreatePR: () => Promise<unknown>;
  onDismiss: () => void;
  feedbackEnabled?: boolean;
}

const RUNNING_STATUSES = new Set<ProjectOperationStatus>([
  'queued',
  'cloning',
  'scanning',
  'applying',
]);

function mapStatus(s: ProjectOperationStatus): import('../types/operation').OperationStatus {
  const mapping: Partial<Record<ProjectOperationStatus, string>> = {
    queued: 'connecting',
    cloning: 'cloning',
    scanning: 'checking',
    applying: 'applying',
  };
  return (mapping[s] ?? s) as import('../types/operation').OperationStatus;
}

export function OperationPanel({
  state,
  onApprove,
  onCancel,
  onCreatePR,
  onDismiss,
  feedbackEnabled,
}: OperationPanelProps) {
  const [prCreating, setPrCreating] = useState(false);
  const [prError, setPrError] = useState<string | null>(null);

  const handleCancel = useCallback(() => {
    onCancel().catch(() => {});
  }, [onCancel]);

  const handleApprove = useCallback(
    (ids: string[]) => {
      onApprove(ids).catch(() => {});
    },
    [onApprove],
  );

  const handleCreatePR = useCallback(async () => {
    setPrCreating(true);
    setPrError(null);
    try {
      await onCreatePR();
    } catch (err) {
      setPrError(err instanceof Error ? err.message : 'Failed to create PR');
    } finally {
      setPrCreating(false);
    }
  }, [onCreatePR]);

  if (!state || state.status === 'cancelled') {
    return null;
  }

  const status = state.status;

  if (RUNNING_STATUSES.has(status)) {
    if (status === 'queued') {
      return (
        <Card style={{ marginBottom: 16 }}>
          <CardBody style={{ textAlign: 'center', padding: '32px 24px' }}>
            <Spinner size="lg" />
            <div style={{ marginTop: 12, fontSize: 16 }}>Starting operation...</div>
            <Button variant="link" onClick={handleCancel} style={{ marginTop: 8 }}>
              Cancel
            </Button>
          </CardBody>
        </Card>
      );
    }

    const progressEntries: OperationProgress[] = state.progress.map((p) => ({
      phase: p.phase,
      message: p.message,
      timestamp: new Date(p.timestamp).getTime(),
      progress: p.progress ?? undefined,
      level: p.level ?? undefined,
    }));

    return (
      <OperationProgressPanel
        status={mapStatus(status)}
        progress={progressEntries}
        onCancel={handleCancel}
      />
    );
  }

  if (status === 'awaiting_approval' && state.proposals) {
    return (
      <ProposalReviewPanel
        proposals={state.proposals.map((p) => ({
          id: p.id,
          rule_id: p.rule_id,
          file: p.file,
          tier: p.tier,
          confidence: p.confidence,
          explanation: p.explanation,
          diff_hunk: p.diff_hunk,
          status: p.status,
          suggestion: p.suggestion,
          line_start: p.line_start,
        }))}
        onApprove={handleApprove}
        feedbackEnabled={feedbackEnabled ?? false}
        scanId={state.scan_id}
      />
    );
  }

  if (status === 'completed' || status === 'submitting_pr' || status === 'pr_submitted') {
    const resultData: OperationResult | null = state.result
      ? {
          total_violations: state.result.total_violations,
          fixable: state.result.fixable,
          ai_candidate: state.result.ai_proposed,
          ai_proposed: state.result.ai_proposed,
          ai_declined: state.result.ai_declined,
          ai_accepted: state.result.ai_accepted,
          manual_review: state.result.manual_review,
          remediated_count: state.result.remediated_count,
        }
      : null;

    if (!resultData) {
      return (
        <Card style={{ marginBottom: 16, borderLeft: '4px solid var(--pf-t--global--color--status--success--default)' }}>
          <CardBody style={{ textAlign: 'center', padding: 32 }}>
            <div style={{ fontSize: 48, color: 'var(--pf-t--global--color--status--success--default)' }}>&#10003;</div>
            <h2>Operation Complete</h2>
            <Button variant="link" onClick={onDismiss} style={{ marginTop: 8 }}>
              Dismiss
            </Button>
          </CardBody>
        </Card>
      );
    }

    const showCreatePR =
      status === 'completed' &&
      state.scan_type === 'remediate' &&
      (resultData.remediated_count ?? 0) > 0 &&
      !state.pr_url;

    return (
      <OperationResultCard
        result={resultData}
        isRemediate={state.scan_type === 'remediate'}
        onDismiss={onDismiss}
        onCreatePR={showCreatePR ? handleCreatePR : undefined}
        prCreating={prCreating || status === 'submitting_pr'}
        prUrl={state.pr_url}
        prError={prError}
        scanId={state.scan_id}
      />
    );
  }

  if (status === 'failed') {
    return (
      <Card style={{ marginBottom: 16, borderLeft: '4px solid var(--pf-t--global--color--status--danger--default)' }}>
        <CardBody>
          <h3 style={{ color: 'var(--pf-t--global--color--status--danger--default)' }}>
            Operation Failed
          </h3>
          <p>{state.error || 'An unknown error occurred.'}</p>
          <Flex gap={{ default: 'gapSm' }} style={{ marginTop: 8 }}>
            <FlexItem>
              <Button variant="link" onClick={onDismiss}>Dismiss</Button>
            </FlexItem>
          </Flex>
        </CardBody>
      </Card>
    );
  }

  if (status === 'expired') {
    return (
      <Card style={{ marginBottom: 16, borderLeft: '4px solid var(--pf-t--global--color--status--warning--default)' }}>
        <CardBody>
          <h3>Session Expired</h3>
          <p>This operation session has expired. Please start a new one.</p>
          <Button variant="link" onClick={onDismiss}>Dismiss</Button>
        </CardBody>
      </Card>
    );
  }

  return null;
}
