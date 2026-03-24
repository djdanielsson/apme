import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import {
  Button,
  Card,
  CardBody,
  Checkbox,
  ExpandableSection,
  Flex,
  FlexItem,
  Label,
  Progress,
  Split,
  SplitItem,
  TextInput,
} from '@patternfly/react-core';
import JSZip from 'jszip';
import { AI_MODEL_STORAGE_KEY } from './SettingsPage';
import {
  useSessionStream,
  type Patch,
  type Proposal,
  type SessionStatus,
  type ProgressEntry,
  type Tier1Result,
  type SessionResult,
} from '../hooks/useSessionStream';

export function PlaygroundPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [ansibleVersion, setAnsibleVersion] = useState('');
  const [collections, setCollections] = useState('');
  const [enableAi, setEnableAi] = useState(true);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);

  const {
    status,
    progress,
    scanId,
    tier1,
    proposals,
    result,
    error,
    startSession,
    approve,
    cancel,
    reset,
  } = useSessionStream();

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (status !== 'idle') return;
      const dropped = Array.from(e.dataTransfer.files);
      setFiles((prev) => [...prev, ...dropped]);
    },
    [status],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!e.target.files) return;
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
      e.target.value = '';
    },
    [],
  );

  const removeFile = useCallback((idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleSubmit = useCallback(() => {
    if (files.length === 0) return;
    const colls = collections
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
    startSession(files, {
      ansibleVersion,
      collections: colls.length ? colls : undefined,
      enableAi,
      aiModel: enableAi ? (localStorage.getItem(AI_MODEL_STORAGE_KEY) ?? undefined) : undefined,
    });
  }, [files, ansibleVersion, collections, enableAi, startSession]);

  const handleReset = useCallback(() => {
    reset();
    setFiles([]);
  }, [reset]);

  const isRunning =
    status === 'connecting' ||
    status === 'uploading' ||
    status === 'scanning' ||
    status === 'applying';

  return (
    <PageLayout>
      <PageHeader
        title="Playground"
        description="Ad-hoc scan — upload files directly for a quick lint check. Results are not persisted to any project."
      />

      <div style={{ padding: '0 24px 24px' }}>
        {status === 'idle' && (
          <Card>
            <CardBody>
              <div
                className={`apme-drop-zone ${isDragOver ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="apme-drop-icon">+</div>
                <div className="apme-drop-text">
                  Drop Ansible files here or click to browse
                </div>
                <div className="apme-drop-hint">
                  Supports individual files or entire directories
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".yml,.yaml,.json,.j2,.jinja2,.cfg,.ini,.toml,.py,.sh"
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />
              </div>

              <div style={{ marginTop: 8 }}>
                <Button variant="secondary" onClick={() => dirInputRef.current?.click()}>
                  Select Directory
                </Button>
                <input
                  ref={dirInputRef}
                  type="file"
                  /* @ts-expect-error webkitdirectory is non-standard */
                  webkitdirectory=""
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />
              </div>

              {files.length > 0 && (
                <div className="apme-file-list">
                  <h3>
                    {files.length} file{files.length !== 1 ? 's' : ''} selected
                  </h3>
                  <ul>
                    {files.map((f, i) => (
                      <li key={`${f.name}-${i}`} className="apme-file-item">
                        <span className="apme-file-name">
                          {(f as File & { webkitRelativePath?: string })
                            .webkitRelativePath || f.name}
                        </span>
                        <span className="apme-file-size">
                          {(f.size / 1024).toFixed(1)} KB
                        </span>
                        <Button variant="plain" onClick={() => removeFile(i)} aria-label={`Remove ${f.name}`} size="sm">
                          &times;
                        </Button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <ExpandableSection toggleText="Advanced Options" style={{ marginTop: 16 }}>
                <Flex direction={{ default: 'column' }} gap={{ default: 'gapMd' }}>
                  <FlexItem>
                    <label htmlFor="ansible-version" style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>
                      Ansible Core Version
                    </label>
                    <TextInput
                      id="ansible-version"
                      placeholder="e.g. 2.16"
                      value={ansibleVersion}
                      onChange={(_e, v) => setAnsibleVersion(v)}
                    />
                  </FlexItem>
                  <FlexItem>
                    <label htmlFor="collections" style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>
                      Collections (comma-separated)
                    </label>
                    <TextInput
                      id="collections"
                      placeholder="e.g. ansible.posix, community.general"
                      value={collections}
                      onChange={(_e, v) => setCollections(v)}
                    />
                  </FlexItem>
                  <FlexItem>
                    <Checkbox
                      id="enable-ai"
                      label="Enable AI-assisted remediation (Tier 2)"
                      isChecked={enableAi}
                      onChange={(_e, checked) => setEnableAi(checked)}
                    />
                  </FlexItem>
                </Flex>
              </ExpandableSection>

              <Button
                variant="primary"
                isDisabled={files.length === 0}
                onClick={handleSubmit}
                style={{ marginTop: 16 }}
              >
                Start Scan
              </Button>
            </CardBody>
          </Card>
        )}

        {isRunning && (
          <ScanProgress status={status} progress={progress} onCancel={cancel} />
        )}

        {status === 'tier1_done' && tier1 && (
          <Tier1Results tier1={tier1} />
        )}

        {status === 'awaiting_approval' && proposals.length > 0 && (
          <>
            {tier1 && <Tier1Results tier1={tier1} />}
            <ProposalApproval proposals={proposals} onApprove={approve} />
          </>
        )}

        {status === 'complete' && result && (
          <SessionComplete result={result} scanId={scanId} tier1={tier1} />
        )}
        {status === 'complete' && !result && (
          <Card style={{ textAlign: 'center', padding: 48 }}>
            <CardBody>
              <div style={{ fontSize: 48, color: 'var(--pf-t--global--color--status--success--default)' }}>&#10003;</div>
              <h2>Scan Complete</h2>
              <Button variant="primary" onClick={handleReset} style={{ marginTop: 16 }}>
                Scan More Files
              </Button>
            </CardBody>
          </Card>
        )}

        {status === 'error' && (
          <Card style={{ textAlign: 'center', padding: 48 }}>
            <CardBody>
              <h2 style={{ color: 'var(--pf-t--global--color--status--danger--default)' }}>Scan Failed</h2>
              <p style={{ opacity: 0.7 }}>{error}</p>
              <Button variant="primary" onClick={handleReset}>
                Try Again
              </Button>
            </CardBody>
          </Card>
        )}
      </div>
    </PageLayout>
  );
}


function ScanProgress({
  status,
  progress,
  onCancel,
}: {
  status: SessionStatus;
  progress: ProgressEntry[];
  onCancel: () => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [progress.length]);

  const label =
    status === 'connecting'
      ? 'Connecting...'
      : status === 'uploading'
        ? 'Uploading files...'
        : status === 'applying'
          ? 'Applying approved fixes...'
          : 'Scanning...';

  return (
    <Card>
      <CardBody>
        <Split hasGutter>
          <SplitItem isFilled><h2>{label}</h2></SplitItem>
          <SplitItem><Button variant="secondary" onClick={onCancel}>Cancel</Button></SplitItem>
        </Split>
        <Progress value={undefined} style={{ marginTop: 16 }} />
        <div className="apme-timeline" style={{ marginTop: 16 }}>
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

function Tier1Results({ tier1 }: { tier1: Tier1Result }) {
  const patchCount = tier1.patches.length;
  const formatCount = tier1.format_diffs.length;
  const [expanded, setExpanded] = useState(false);

  if (patchCount === 0 && formatCount === 0) return null;

  return (
    <Card style={{ marginBottom: 16 }}>
      <CardBody>
        <Split hasGutter>
          <SplitItem>
            <Label color="green" isCompact>Auto-Fix</Label>
          </SplitItem>
          <SplitItem isFilled>
            <h3>
              Tier 1 — {patchCount} fix{patchCount !== 1 ? 'es' : ''} applied
              {formatCount > 0 && `, ${formatCount} formatted`}
            </h3>
          </SplitItem>
          <SplitItem>
            <Button variant="secondary" onClick={() => setExpanded(!expanded)} size="sm">
              {expanded ? 'Collapse' : 'Show Diffs'}
            </Button>
          </SplitItem>
        </Split>
        {expanded && (
          <div className="apme-tier1-diffs" style={{ marginTop: 16 }}>
            {tier1.patches.map((p, i) => (
              <div key={i} className="apme-diff-block">
                <div className="apme-diff-file">
                  <span className="apme-file-name">{p.file}</span>
                  {p.applied_rules.length > 0 && (
                    <span className="apme-diff-rules">{p.applied_rules.join(', ')}</span>
                  )}
                </div>
                {p.diff && <pre className="apme-diff-content">{p.diff}</pre>}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function ProposalApproval({
  proposals,
  onApprove,
}: {
  proposals: Proposal[];
  onApprove: (ids: string[]) => void;
}) {
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
    <Card>
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
        <div className="apme-proposals-list">
          {proposals.map((p) => (
            <div
              key={p.id}
              className={`apme-proposal-card ${selected.has(p.id) ? 'selected' : ''}`}
              onClick={() => toggle(p.id)}
            >
              <input type="checkbox" checked={selected.has(p.id)} readOnly className="apme-proposal-checkbox" />
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

function SessionComplete({
  result,
  scanId,
  tier1,
}: {
  result: SessionResult;
  scanId: string | null;
  tier1: Tier1Result | null;
}) {
  const totalPatches = result.patches.length + (tier1?.patches.length ?? 0);
  const remaining = result.remaining_violations.length;

  const patchedFiles = useMemo(() => {
    const byPath = new Map<string, Patch>();
    for (const p of tier1?.patches ?? []) {
      if (p.patched) byPath.set(p.file, p);
    }
    for (const p of result.patches) {
      if (p.patched) byPath.set(p.file, p);
    }
    return byPath;
  }, [tier1, result]);

  const [downloading, setDownloading] = useState(false);

  const handleDownload = useCallback(async () => {
    if (patchedFiles.size === 0) return;
    setDownloading(true);
    try {
      const zip = new JSZip();
      for (const [path, patch] of patchedFiles) {
        const bytes = Uint8Array.from(atob(patch.patched!), (c) => c.charCodeAt(0));
        zip.file(path, bytes);
      }
      const blob = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `apme-fixed-${scanId ?? 'files'}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }, [patchedFiles, scanId]);

  return (
    <Card style={{ textAlign: 'center', padding: 32 }}>
      <CardBody>
        <div style={{ fontSize: 48, color: 'var(--pf-t--global--color--status--success--default)' }}>&#10003;</div>
        <h2>Scan Complete</h2>
        <Split hasGutter style={{ justifyContent: 'center', margin: '16px 0' }}>
          <SplitItem>
            <div style={{ fontSize: 32, fontWeight: 700, color: 'var(--pf-t--global--color--status--success--default)' }}>{totalPatches}</div>
            <div style={{ opacity: 0.7 }}>Fixed</div>
          </SplitItem>
          <SplitItem>
            <div style={{
              fontSize: 32,
              fontWeight: 700,
              color: remaining > 0
                ? 'var(--pf-t--global--color--status--warning--default)'
                : 'var(--pf-t--global--color--status--success--default)',
            }}>
              {remaining}
            </div>
            <div style={{ opacity: 0.7 }}>Remaining</div>
          </SplitItem>
        </Split>
        {patchedFiles.size > 0 && (
          <Button variant="primary" onClick={handleDownload} isDisabled={downloading} style={{ marginBottom: 16 }}>
            {downloading ? 'Preparing...' : `Download Fixed Files (${patchedFiles.size})`}
          </Button>
        )}
        {remaining > 0 && (
          <ExpandableSection toggleText={`Remaining Violations (${remaining})`} style={{ textAlign: 'left', maxWidth: 700, margin: '8px auto 0' }}>
            <div className="apme-remaining-list">
              {result.remaining_violations.map((v, i) => (
                <div key={i} className="apme-remaining-item">
                  <span className="apme-rule-id">{v.rule_id}</span>
                  <span className="apme-file-name">{v.file}</span>
                  <span>{v.message}</span>
                </div>
              ))}
            </div>
          </ExpandableSection>
        )}
      </CardBody>
    </Card>
  );
}
