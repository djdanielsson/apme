import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageLayout } from '@ansible/ansible-ui-framework';
import {
  Bullseye,
  Card,
  CardBody,
  CardHeader,
  Flex,
  Label,
  Title,
} from '@patternfly/react-core';
import { getDashboardSummary, getDashboardRankings } from '../services/api';
import type { DashboardSummary, ProjectRanking } from '../types/api';
import { timeAgo } from '../services/format';
import { healthLabelColor } from '../components/severity';

function MetricCard({ title, count, suffix, color }: { title: string; count: number; suffix?: string; color?: string }) {
  return (
    <Card isCompact>
      <CardBody>
        <Bullseye>
          <Flex
            direction={{ default: 'column' }}
            spaceItems={{ default: 'spaceItemsXs' }}
            alignItems={{ default: 'alignItemsCenter' }}
          >
            <span style={{ fontSize: 32, lineHeight: 1, fontWeight: 700, color }}>
              {count}{suffix}
            </span>
            <Title headingLevel="h3" size="md">{title}</Title>
          </Flex>
        </Bullseye>
      </CardBody>
    </Card>
  );
}

function HealthBadge({ score }: { score: number }) {
  return <Label color={healthLabelColor(score)} isCompact>{score}</Label>;
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
      <div className="apme-dashboard-scroll">
        <Title headingLevel="h1" style={{ padding: '16px 24px 0 24px' }}>Dashboard</Title>

        <div className="apme-dashboard-metrics">
          <MetricCard title="Projects" count={summary?.total_projects ?? 0} />
          <MetricCard title="Avg Health" count={summary ? Math.round(summary.avg_health_score) : 0} />
          <MetricCard title="Current Violations" count={summary?.current_violations ?? 0} color="var(--apme-sev-high)" />
          <MetricCard title="Current Fixable" count={summary?.current_fixable ?? 0} color="var(--apme-green)" />
          <MetricCard title="Total Checks" count={summary?.total_scans ?? 0} />
          <MetricCard title="AI Candidates" count={summary?.current_ai_candidates ?? 0} color="var(--apme-sev-medium)" />
          <MetricCard title="Total Violations" count={summary?.total_violations ?? 0} />
          <MetricCard title="Total Remediated" count={summary?.total_fixed ?? 0} color="var(--apme-green)" />
        </div>

        <div className="apme-dashboard-rankings">
          <RankingCard title="Top 10 Cleanest" loading={loading} rankings={cleanest} navigate={navigate} />
          <RankingCard title="Top 10 Most Violations" loading={loading} rankings={dirtiest} navigate={navigate} />
          <RankingCard title="Stale Projects" loading={loading} rankings={stale} navigate={navigate} showDaysSince />
          <RankingCard title="Most Active" loading={loading} rankings={mostScanned} navigate={navigate} showScanCount />
        </div>
      </div>
    </PageLayout>
  );
}

function RankingCard({
  title,
  loading,
  rankings,
  navigate,
  showDaysSince,
  showScanCount,
}: {
  title: string;
  loading: boolean;
  rankings: ProjectRanking[];
  navigate: ReturnType<typeof useNavigate>;
  showDaysSince?: boolean;
  showScanCount?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <Title headingLevel="h3" size="lg">{title}</Title>
      </CardHeader>
      <CardBody style={{ paddingInline: 0 }}>
        {loading ? (
          <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
        ) : rankings.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No project data yet.</div>
        ) : (
          <table className="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid" style={{ tableLayout: 'auto' }}>
            <thead>
              <tr role="row">
                <th role="columnheader" style={{ paddingLeft: 24 }}>Project</th>
                <th role="columnheader">Health</th>
                <th role="columnheader">Violations</th>
                {showDaysSince && <th role="columnheader">Days Since Check</th>}
                {showScanCount && <th role="columnheader">Checks</th>}
                <th role="columnheader" style={{ paddingRight: 24 }}>Last Checked</th>
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
                  <td role="cell" style={{ fontWeight: 600, paddingLeft: 24 }}>{r.name}</td>
                  <td role="cell"><HealthBadge score={r.health_score} /></td>
                  <td role="cell">{r.total_violations}</td>
                  {showDaysSince && (
                    <td role="cell">{r.days_since_last_scan != null ? r.days_since_last_scan : '—'}</td>
                  )}
                  {showScanCount && <td role="cell">{r.scan_count}</td>}
                  <td role="cell" style={{ opacity: 0.7, paddingRight: 24 }}>
                    {r.last_scanned_at ? timeAgo(r.last_scanned_at) : 'Never'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardBody>
    </Card>
  );
}
