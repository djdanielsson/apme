import { useEffect, useRef } from 'react';
import {
  Button,
  Card,
  CardBody,
  Label,
  Progress,
  Split,
  SplitItem,
} from '@patternfly/react-core';
import type { OperationProgress, OperationStatus } from '../types/operation';

export interface OperationProgressPanelProps {
  status: OperationStatus;
  progress: OperationProgress[];
  onCancel: () => void;
}

const STATUS_LABELS: Partial<Record<OperationStatus, string>> = {
  connecting: 'Connecting...',
  preparing: 'Preparing...',
  scanning: 'Scanning...',
  applying: 'Applying approved fixes...',
};

export function OperationProgressPanel({
  status,
  progress,
  onCancel,
}: OperationProgressPanelProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [progress.length]);

  const label = STATUS_LABELS[status] ?? 'Processing...';

  return (
    <Card style={{ marginBottom: 16 }}>
      <CardBody>
        <Split hasGutter>
          <SplitItem isFilled><h2>{label}</h2></SplitItem>
          <SplitItem><Button variant="secondary" onClick={onCancel}>Cancel</Button></SplitItem>
        </Split>
        <Progress value={undefined} style={{ marginTop: 16 }} />
        <div className="apme-timeline" style={{ marginTop: 16, maxHeight: 200, overflowY: 'auto' }}>
          {progress.map((entry, i) => (
            <div key={i} className="apme-timeline-entry">
              <Label isCompact>{entry.phase}</Label>
              <span style={{ marginLeft: 8 }}>{entry.message}</span>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </CardBody>
    </Card>
  );
}
