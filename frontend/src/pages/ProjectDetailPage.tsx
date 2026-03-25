import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import {
  Button,
  Card,
  CardBody,
  Flex,
  FlexItem,
  Label,
  Split,
  SplitItem,
  Tab,
  Tabs,
  TabTitleText,
  TextInput,
} from '@patternfly/react-core';
import { deleteProject, getProject, listProjectScans, listProjectViolations, updateProject } from '../services/api';
import type { ProjectDetail, ScanSummary, ViolationDetail } from '../types/api';
import type { OperationStatus, OperationProgress, OperationProposal, OperationResult } from '../types/operation';
import { StatusBadge } from '../components/StatusBadge';
import { ScanOptionsForm } from '../components/ScanOptionsForm';
import { OperationProgressPanel } from '../components/OperationProgressPanel';
import { ProposalReviewPanel } from '../components/ProposalReviewPanel';
import { OperationResultCard } from '../components/OperationResultCard';
import { timeAgo } from '../services/format';
import { useProjectOperation, type ProjectOperationOptions } from '../hooks/useProjectOperation';
import { AI_MODEL_STORAGE_KEY } from './SettingsPage';
import { useNavigate } from 'react-router-dom';

function mapProjectStatus(s: string): OperationStatus {
  if (s === 'cloning') return 'preparing';
  return s as OperationStatus;
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [violations, setViolations] = useState<ViolationDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);

  const [ansibleVersion, setAnsibleVersion] = useState('');
  const [collections, setCollections] = useState('');
  const [enableAi, setEnableAi] = useState(true);

  const {
    status: rawStatus,
    progress: rawProgress,
    proposals: rawProposals,
    result: rawResult,
    error: opError,
    startOperation,
    approve: opApprove,
    cancel: opCancel,
    reset: opReset,
  } = useProjectOperation(projectId || '');

  const opStatus = mapProjectStatus(rawStatus);
  const opProgress: OperationProgress[] = rawProgress.map((p) => ({
    phase: p.phase,
    message: p.message,
    timestamp: p.timestamp,
  }));
  const opProposals: OperationProposal[] = rawProposals.map((p) => ({
    id: p.id,
    rule_id: p.rule_id,
    file: p.file,
    tier: p.tier,
    confidence: p.confidence,
  }));
  const opResult: OperationResult | null = rawResult ? {
    total_violations: rawResult.total_violations,
    auto_fixable: rawResult.auto_fixable,
    ai_candidate: rawResult.ai_candidate,
    manual_review: rawResult.manual_review,
  } : null;

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const proj = await getProject(projectId);
      setProject(proj);
      const [scanResult, violResult] = await Promise.allSettled([
        listProjectScans(projectId, 20, 0),
        listProjectViolations(projectId, 100, 0),
      ]);
      if (scanResult.status === 'fulfilled') setScans(scanResult.value.items);
      if (violResult.status === 'fulfilled') setViolations(violResult.value);
    } catch {
      setProject(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (opStatus === 'complete') fetchData();
  }, [opStatus, fetchData]);

  const handleScan = useCallback((fix: boolean) => {
    const colls = collections.split(',').map((c) => c.trim()).filter(Boolean);
    const opts: ProjectOperationOptions = {
      fix,
      ansible_version: ansibleVersion || undefined,
      collection_specs: colls.length ? colls : undefined,
      enable_ai: enableAi,
      ai_model: enableAi ? (localStorage.getItem(AI_MODEL_STORAGE_KEY) ?? undefined) : undefined,
    };
    setActiveTab(0);
    startOperation(opts);
  }, [ansibleVersion, collections, enableAi, startOperation]);

  useEffect(() => {
    if (searchParams.get('action') === 'scan' && project && rawStatus === 'idle') {
      setSearchParams({}, { replace: true });
      handleScan(false);
    }
  }, [searchParams, project, rawStatus, setSearchParams, handleScan]);

  const handleDelete = useCallback(async () => {
    if (!projectId) return;
    if (!window.confirm('Delete this project and all its scan history?')) return;
    await deleteProject(projectId);
    navigate('/projects');
  }, [projectId, navigate]);

  const [editName, setEditName] = useState('');
  const [editUrl, setEditUrl] = useState('');
  const [editBranch, setEditBranch] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (project) {
      setEditName(project.name);
      setEditUrl(project.repo_url);
      setEditBranch(project.branch);
    }
  }, [project]);

  const handleSave = useCallback(async () => {
    if (!projectId || !project) return;
    setSaving(true);
    try {
      const updates: Record<string, string> = {};
      if (editName !== project.name) updates.name = editName;
      if (editUrl !== project.repo_url) updates.repo_url = editUrl;
      if (editBranch !== project.branch) updates.branch = editBranch;
      if (Object.keys(updates).length > 0) {
        await updateProject(projectId, updates);
        fetchData();
      }
    } finally {
      setSaving(false);
    }
  }, [projectId, project, editName, editUrl, editBranch, fetchData]);

  if (loading && !project) {
    return (
      <PageLayout>
        <PageHeader title="Project" />
        <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
      </PageLayout>
    );
  }

  if (!project) {
    return (
      <PageLayout>
        <PageHeader title="Project Not Found" />
        <div style={{ padding: 48, textAlign: 'center' }}>
          <p>This project does not exist.</p>
          <Button variant="primary" component={(props: object) => <Link {...props} to="/projects" />}>
            Back to Projects
          </Button>
        </div>
      </PageLayout>
    );
  }

  const isRunning = opStatus === 'connecting' || opStatus === 'preparing' || opStatus === 'scanning' || opStatus === 'applying';
  const operationActive = isRunning || opStatus === 'awaiting_approval' || (opStatus === 'complete' && opResult != null) || opStatus === 'error';

  return (
    <PageLayout>
      <PageHeader
        title={project.name}
        description={`${project.repo_url} (${project.branch})`}
      />

      <div style={{ padding: '0 24px 24px' }}>
        <Tabs activeKey={activeTab} onSelect={(_e, k) => setActiveTab(k as number)}>
          <Tab eventKey={0} title={<TabTitleText>Overview</TabTitleText>}>
            <div style={{ marginTop: 16 }}>
              {operationActive ? (
                <>
                  {isRunning && (
                    <OperationProgressPanel status={opStatus} progress={opProgress} onCancel={opCancel} />
                  )}

                  {opStatus === 'awaiting_approval' && opProposals.length > 0 && (
                    <ProposalReviewPanel proposals={opProposals} onApprove={opApprove} />
                  )}

                  {opStatus === 'complete' && opResult && (
                    <OperationResultCard result={opResult} onDismiss={opReset} />
                  )}

                  {opStatus === 'error' && (
                    <Card style={{ marginBottom: 16, borderLeft: '4px solid var(--pf-t--global--color--status--danger--default)' }}>
                      <CardBody>
                        <h3 style={{ color: 'var(--pf-t--global--color--status--danger--default)' }}>Error</h3>
                        <p>{opError}</p>
                        <Button variant="link" onClick={opReset}>Dismiss</Button>
                      </CardBody>
                    </Card>
                  )}
                </>
              ) : project.scan_count === 0 ? (
                <Card style={{ marginBottom: 16 }}>
                  <CardBody style={{ textAlign: 'center', padding: '48px 24px' }}>
                    <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No scans yet</div>
                    <div style={{ opacity: 0.7, marginBottom: 24 }}>
                      Run the first scan to assess this project.
                    </div>
                    <Flex justifyContent={{ default: 'justifyContentCenter' }} gap={{ default: 'gapSm' }}>
                      <Button variant="primary" isDisabled={isRunning} onClick={() => handleScan(false)}>Scan Now</Button>
                      <Button variant="secondary" isDisabled={isRunning} onClick={() => handleScan(true)}>Scan &amp; Fix</Button>
                    </Flex>
                  </CardBody>
                </Card>
              ) : (
                <>
                  <Flex gap={{ default: 'gapSm' }} style={{ marginBottom: 16 }}>
                    <Button variant="primary" isDisabled={isRunning} onClick={() => handleScan(false)}>Scan</Button>
                    <Button variant="secondary" isDisabled={isRunning} onClick={() => handleScan(true)}>Scan &amp; Fix</Button>
                  </Flex>

                  <Split hasGutter style={{ marginBottom: 16 }}>
                    <SplitItem>
                      <Card>
                        <CardBody>
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 36, fontWeight: 700 }}>{project.health_score}</div>
                            <div style={{ opacity: 0.7 }}>Health Score</div>
                          </div>
                        </CardBody>
                      </Card>
                    </SplitItem>
                    <SplitItem>
                      <Card>
                        <CardBody>
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 36, fontWeight: 700 }}>{project.total_violations}</div>
                            <div style={{ opacity: 0.7 }}>Violations</div>
                          </div>
                        </CardBody>
                      </Card>
                    </SplitItem>
                    <SplitItem>
                      <Card>
                        <CardBody>
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 36, fontWeight: 700 }}>{project.scan_count}</div>
                            <div style={{ opacity: 0.7 }}>Scans</div>
                          </div>
                        </CardBody>
                      </Card>
                    </SplitItem>
                    <SplitItem>
                      <Card>
                        <CardBody>
                          <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 36, fontWeight: 700 }}>
                              {project.last_scanned_at ? timeAgo(project.last_scanned_at) : 'Never'}
                            </div>
                            <div style={{ opacity: 0.7 }}>Last Scanned</div>
                          </div>
                        </CardBody>
                      </Card>
                    </SplitItem>
                  </Split>

                  {Object.keys(project.severity_breakdown).length > 0 && (
                    <Card style={{ marginBottom: 16 }}>
                      <CardBody>
                        <h3>Severity Breakdown</h3>
                        <Flex gap={{ default: 'gapLg' }} style={{ marginTop: 8 }}>
                          {Object.entries(project.severity_breakdown).map(([level, count]) => (
                            <FlexItem key={level}>
                              <Label
                                color={level === 'error' ? 'red' : level === 'warning' ? 'orange' : 'blue'}
                                isCompact
                              >
                                {level}: {count}
                              </Label>
                            </FlexItem>
                          ))}
                        </Flex>
                      </CardBody>
                    </Card>
                  )}
                </>
              )}
            </div>
          </Tab>

          <Tab eventKey={1} title={<TabTitleText>Scans</TabTitleText>}>
            <div style={{ marginTop: 16 }}>
              <Card style={{ marginBottom: 16 }}>
                <CardBody>
                  <h3>Scan Options</h3>
                  <ScanOptionsForm
                    ansibleVersion={ansibleVersion}
                    onAnsibleVersionChange={setAnsibleVersion}
                    collections={collections}
                    onCollectionsChange={setCollections}
                    enableAi={enableAi}
                    onEnableAiChange={setEnableAi}
                    idPrefix="proj"
                  />
                  <Flex gap={{ default: 'gapSm' }} style={{ marginTop: 12 }}>
                    <Button variant="primary" isDisabled={isRunning} onClick={() => handleScan(false)}>Scan</Button>
                    <Button variant="secondary" isDisabled={isRunning} onClick={() => handleScan(true)}>Scan &amp; Fix</Button>
                    {isRunning && <Button variant="link" onClick={opCancel}>Cancel</Button>}
                  </Flex>
                </CardBody>
              </Card>

              <h3 style={{ marginBottom: 8 }}>Scan History</h3>
              {scans.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No scans recorded yet.</div>
              ) : (
                <table className="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid">
                  <thead>
                    <tr role="row">
                      <th role="columnheader">Type</th>
                      <th role="columnheader">Status</th>
                      <th role="columnheader">Violations</th>
                      <th role="columnheader">Auto-Fix</th>
                      <th role="columnheader">AI</th>
                      <th role="columnheader">Manual</th>
                      <th role="columnheader">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scans.map((scan) => (
                      <tr
                        key={scan.scan_id}
                        role="row"
                        tabIndex={0}
                        onClick={() => navigate(`/scans/${scan.scan_id}`)}
                        onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/scans/${scan.scan_id}`); }}
                        style={{ cursor: 'pointer' }}
                      >
                        <td role="cell">
                          <span className={`apme-badge ${scan.scan_type === 'fix' ? 'passed' : 'running'}`}>{scan.scan_type}</span>
                        </td>
                        <td role="cell"><StatusBadge violations={scan.total_violations} scanType={scan.scan_type} /></td>
                        <td role="cell">{scan.total_violations}</td>
                        <td role="cell"><span className="apme-count-success">{scan.auto_fixable}</span></td>
                        <td role="cell">{scan.ai_candidate}</td>
                        <td role="cell"><span className="apme-count-error">{scan.manual_review}</span></td>
                        <td role="cell" style={{ opacity: 0.7 }}>{timeAgo(scan.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Tab>

          <Tab eventKey={2} title={<TabTitleText>Violations</TabTitleText>}>
            <div style={{ marginTop: 16 }}>
              {violations.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No violations in the latest scan.</div>
              ) : (
                <table className="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid">
                  <thead>
                    <tr role="row">
                      <th role="columnheader">Rule</th>
                      <th role="columnheader">Severity</th>
                      <th role="columnheader">File</th>
                      <th role="columnheader">Line</th>
                      <th role="columnheader">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {violations.map((v) => (
                      <tr key={v.id} role="row">
                        <td role="cell"><span className="apme-rule-id">{v.rule_id}</span></td>
                        <td role="cell">
                          <Label
                            color={v.level === 'error' ? 'red' : v.level === 'warning' ? 'orange' : 'blue'}
                            isCompact
                          >
                            {v.level}
                          </Label>
                        </td>
                        <td role="cell" style={{ fontFamily: 'var(--pf-t--global--font--family--mono)' }}>{v.file}</td>
                        <td role="cell">{v.line ?? ''}</td>
                        <td role="cell">{v.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </Tab>

          <Tab eventKey={3} title={<TabTitleText>Settings</TabTitleText>}>
            <div style={{ marginTop: 16, maxWidth: 600 }}>
              <Card>
                <CardBody>
                  <Flex direction={{ default: 'column' }} gap={{ default: 'gapMd' }}>
                    <FlexItem>
                      <label htmlFor="edit-name" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Name</label>
                      <TextInput id="edit-name" value={editName} onChange={(_e, v) => setEditName(v)} />
                    </FlexItem>
                    <FlexItem>
                      <label htmlFor="edit-url" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Repository URL</label>
                      <TextInput id="edit-url" value={editUrl} onChange={(_e, v) => setEditUrl(v)} />
                    </FlexItem>
                    <FlexItem>
                      <label htmlFor="edit-branch" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Branch</label>
                      <TextInput id="edit-branch" value={editBranch} onChange={(_e, v) => setEditBranch(v)} />
                    </FlexItem>
                    <FlexItem>
                      <Flex gap={{ default: 'gapSm' }}>
                        <Button variant="primary" onClick={handleSave} isDisabled={saving}>
                          {saving ? 'Saving...' : 'Save'}
                        </Button>
                        <Button variant="danger" onClick={handleDelete}>Delete Project</Button>
                      </Flex>
                    </FlexItem>
                  </Flex>
                </CardBody>
              </Card>
            </div>
          </Tab>
        </Tabs>
      </div>
    </PageLayout>
  );
}
