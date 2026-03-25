import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import {
  Button,
  Card,
  CardBody,
  EmptyState,
  EmptyStateBody,
  Flex,
  FlexItem,
  Label,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Split,
  SplitItem,
  TextInput,
} from '@patternfly/react-core';
import { SearchIcon } from '@patternfly/react-icons';
import { createProject, listProjects } from '../services/api';
import type { ProjectSummary } from '../types/api';
import { timeAgo } from '../services/format';

function HealthBadge({ score }: { score: number }) {
  let color: 'green' | 'orange' | 'red' = 'green';
  if (score < 50) color = 'red';
  else if (score < 80) color = 'orange';
  return <Label color={color} isCompact>{score}</Label>;
}

function TrendBadge({ trend }: { trend: string }) {
  if (trend === 'improving') return <Label color="green" isCompact>&#9650; Improving</Label>;
  if (trend === 'declining') return <Label color="red" isCompact>&#9660; Declining</Label>;
  return <Label isCompact>&#8212; Stable</Label>;
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState('');
  const [createUrl, setCreateUrl] = useState('');
  const [createBranch, setCreateBranch] = useState('main');
  const [creating, setCreating] = useState(false);

  const fetchProjects = useCallback(() => {
    setLoading(true);
    listProjects(50, 0)
      .then((data) => setProjects(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleCreate = useCallback(async () => {
    if (!createName.trim() || !createUrl.trim()) return;
    setCreating(true);
    try {
      await createProject({ name: createName.trim(), repo_url: createUrl.trim(), branch: createBranch.trim() || 'main' });
      setShowCreate(false);
      setCreateName('');
      setCreateUrl('');
      setCreateBranch('main');
      fetchProjects();
    } catch {
      // keep modal open
    } finally {
      setCreating(false);
    }
  }, [createName, createUrl, createBranch, fetchProjects]);

  return (
    <PageLayout>
      <PageHeader title="Projects" />

      <div style={{ padding: '0 24px 24px' }}>
        <div style={{ marginBottom: 16, textAlign: 'right' }}>
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            Create Project
          </Button>
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
        ) : projects.length === 0 ? (
          <EmptyState>
            <EmptyStateBody>
              No projects defined yet. Create one to get started with SCM-backed scanning.
            </EmptyStateBody>
          </EmptyState>
        ) : (
          <Flex direction={{ default: 'column' }} gap={{ default: 'gapMd' }}>
            {projects.map((proj) => (
              <FlexItem key={proj.id}>
                <Card
                  isClickable
                  onClick={() => navigate(`/projects/${proj.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <CardBody>
                    <Split hasGutter>
                      <SplitItem isFilled>
                        <div style={{ fontWeight: 700, fontSize: 16 }}>{proj.name}</div>
                        <div style={{ opacity: 0.7, fontFamily: 'var(--pf-t--global--font--family--mono)', fontSize: 13, marginTop: 4 }}>
                          {proj.repo_url} ({proj.branch})
                        </div>
                      </SplitItem>
                      <SplitItem>
                        <Flex gap={{ default: 'gapMd' }} alignItems={{ default: 'alignItemsCenter' }}>
                          <FlexItem>
                            <HealthBadge score={proj.health_score} />
                          </FlexItem>
                          <FlexItem>
                            <TrendBadge trend={proj.violation_trend} />
                          </FlexItem>
                          <FlexItem>
                            <span style={{ opacity: 0.7 }}>
                              {proj.scan_count} scan{proj.scan_count !== 1 ? 's' : ''}
                            </span>
                          </FlexItem>
                          <FlexItem>
                            <span style={{ opacity: 0.7 }}>
                              {proj.last_scanned_at ? timeAgo(proj.last_scanned_at) : 'Never scanned'}
                            </span>
                          </FlexItem>
                          <FlexItem>
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={<SearchIcon />}
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/projects/${proj.id}?action=scan`);
                              }}
                            >
                              Scan
                            </Button>
                          </FlexItem>
                        </Flex>
                      </SplitItem>
                    </Split>
                  </CardBody>
                </Card>
              </FlexItem>
            ))}
          </Flex>
        )}
      </div>

      <Modal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        variant="small"
      >
        <ModalHeader title="Create Project" />
        <ModalBody>
          <Flex direction={{ default: 'column' }} gap={{ default: 'gapMd' }}>
            <FlexItem>
              <label htmlFor="proj-name" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Name</label>
              <TextInput id="proj-name" value={createName} onChange={(_e, v) => setCreateName(v)} placeholder="My Ansible Project" />
            </FlexItem>
            <FlexItem>
              <label htmlFor="proj-url" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Repository URL</label>
              <TextInput id="proj-url" value={createUrl} onChange={(_e, v) => setCreateUrl(v)} placeholder="https://github.com/org/repo.git" />
            </FlexItem>
            <FlexItem>
              <label htmlFor="proj-branch" style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>Branch</label>
              <TextInput id="proj-branch" value={createBranch} onChange={(_e, v) => setCreateBranch(v)} placeholder="main" />
            </FlexItem>
          </Flex>
        </ModalBody>
        <ModalFooter>
          <Button variant="primary" onClick={handleCreate} isDisabled={creating || !createName.trim() || !createUrl.trim()}>
            {creating ? 'Creating...' : 'Create'}
          </Button>
          <Button variant="link" onClick={() => setShowCreate(false)}>Cancel</Button>
        </ModalFooter>
      </Modal>
    </PageLayout>
  );
}
