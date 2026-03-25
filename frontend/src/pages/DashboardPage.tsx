import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PageLayout,
  PageHeader,
  PageDashboard,
  PageDashboardCard,
} from '@ansible/ansible-ui-framework';
import { Bullseye, Flex, Label, Title } from '@patternfly/react-core';
import { getDashboardSummary, getDashboardRankings } from '../services/api';
import type { DashboardSummary, ProjectRanking } from '../types/api';
import { timeAgo } from '../services/format';

function MetricCard({ title, count }: { title: string; count: number }) {
  return (
    <PageDashboardCard width="xs" height="xs">
      <Bullseye>
        <Flex
          direction={{ default: 'column' }}
          spaceItems={{ default: 'spaceItemsSm' }}
          alignItems={{ default: 'alignItemsCenter' }}
        >
          <span style={{ fontSize: 'xxx-large', lineHeight: 1 }}>{count}</span>
          <Title headingLevel="h3" size="xl">{title}</Title>
        </Flex>
      </Bullseye>
    </PageDashboardCard>
  );
}

function HealthBadge({ score }: { score: number }) {
  let color: 'green' | 'orange' | 'red' = 'green';
  if (score < 50) color = 'red';
  else if (score < 80) color = 'orange';
  return <Label color={color} isCompact>{score}</Label>;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cleanest, setCleanest] = useState<ProjectRanking[]>([]);
  const [dirtiest, setDirtiest] = useState<ProjectRanking[]>([]);
  const [stale, setStale] = useState<ProjectRanking[]>([]);
  const [mostScanned, setMostScanned] = useState<ProjectRanking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getDashboardSummary(),
      getDashboardRankings('health_score', 'desc', 10),
      getDashboardRankings('health_score', 'asc', 10),
      getDashboardRankings('last_scanned_at', 'desc', 10),
      getDashboardRankings('scan_count', 'desc', 10),
    ])
      .then(([sum, clean, dirty, staleProjects, scanned]) => {
        setSummary(sum);
        setCleanest(clean);
        setDirtiest(dirty);
        setStale(staleProjects);
        setMostScanned(scanned);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageLayout>
      <PageHeader title="Dashboard" />
      <PageDashboard>
        <MetricCard title="Projects" count={summary?.total_projects ?? 0} />
        <MetricCard title="Total Scans" count={summary?.total_scans ?? 0} />
        <MetricCard title="Current Violations" count={summary?.current_violations ?? 0} />
        <MetricCard title="Total Violations" count={summary?.total_violations ?? 0} />
        <MetricCard title="Total Fixed" count={summary?.total_fixed ?? 0} />
        <MetricCard title="Avg Health" count={summary ? Math.round(summary.avg_health_score) : 0} />

        <PageDashboardCard title="Top 10 Cleanest" width="lg" height="md" to="/projects" linkText="View all">
          {loading ? (
            <LoadingPlaceholder />
          ) : cleanest.length === 0 ? (
            <EmptyPlaceholder />
          ) : (
            <RankingTable rankings={cleanest} navigate={navigate} />
          )}
        </PageDashboardCard>

        <PageDashboardCard title="Top 10 Most Violations" width="lg" height="md" to="/projects" linkText="View all">
          {loading ? (
            <LoadingPlaceholder />
          ) : dirtiest.length === 0 ? (
            <EmptyPlaceholder />
          ) : (
            <RankingTable rankings={dirtiest} navigate={navigate} />
          )}
        </PageDashboardCard>

        <PageDashboardCard title="Stale Projects" width="lg" height="md" to="/projects" linkText="View all">
          {loading ? (
            <LoadingPlaceholder />
          ) : stale.length === 0 ? (
            <EmptyPlaceholder />
          ) : (
            <RankingTable rankings={stale} navigate={navigate} showDaysSince />
          )}
        </PageDashboardCard>

        <PageDashboardCard title="Most Scanned" width="lg" height="md" to="/projects" linkText="View all">
          {loading ? (
            <LoadingPlaceholder />
          ) : mostScanned.length === 0 ? (
            <EmptyPlaceholder />
          ) : (
            <RankingTable rankings={mostScanned} navigate={navigate} showScanCount />
          )}
        </PageDashboardCard>
      </PageDashboard>
    </PageLayout>
  );
}

function LoadingPlaceholder() {
  return <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>Loading...</div>;
}

function EmptyPlaceholder() {
  return <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No project data yet.</div>;
}

function RankingTable({
  rankings,
  navigate,
  showDaysSince,
  showScanCount,
}: {
  rankings: ProjectRanking[];
  navigate: ReturnType<typeof useNavigate>;
  showDaysSince?: boolean;
  showScanCount?: boolean;
}) {
  return (
    <table className="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid">
      <thead>
        <tr role="row">
          <th role="columnheader">Project</th>
          <th role="columnheader">Health</th>
          <th role="columnheader">Violations</th>
          {showDaysSince && <th role="columnheader">Days Since Scan</th>}
          {showScanCount && <th role="columnheader">Scans</th>}
          <th role="columnheader">Last Scanned</th>
        </tr>
      </thead>
      <tbody>
        {rankings.map((r) => (
          <tr
            key={r.id}
            role="row"
            tabIndex={0}
            onClick={() => navigate(`/projects/${r.id}`)}
            onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/projects/${r.id}`); }}
            style={{ cursor: 'pointer' }}
          >
            <td role="cell" style={{ fontWeight: 600 }}>{r.name}</td>
            <td role="cell"><HealthBadge score={r.health_score} /></td>
            <td role="cell">{r.total_violations}</td>
            {showDaysSince && (
              <td role="cell">{r.days_since_last_scan != null ? r.days_since_last_scan : '—'}</td>
            )}
            {showScanCount && <td role="cell">{r.scan_count}</td>}
            <td role="cell" style={{ opacity: 0.7 }}>
              {r.last_scanned_at ? timeAgo(r.last_scanned_at) : 'Never'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
