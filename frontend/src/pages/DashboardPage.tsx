import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PageLayout,
  PageHeader,
  PageDashboard,
  PageDashboardCount,
  PageDashboardCard,
} from '@ansible/ansible-ui-framework';
import { listScans, listSessions } from '../services/api';
import type { ScanSummary } from '../types/api';
import { StatusBadge } from '../components/StatusBadge';
import { timeAgo } from '../services/format';

function deduplicateBySession(scans: ScanSummary[]): ScanSummary[] {
  const seen = new Map<string, ScanSummary>();
  for (const scan of scans) {
    if (!seen.has(scan.session_id)) {
      seen.set(scan.session_id, scan);
    }
  }
  return Array.from(seen.values());
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [scans, setScans] = useState<ScanSummary[]>([]);
  const [totalScansCount, setTotalScansCount] = useState(0);
  const [totalSessionsCount, setTotalSessionsCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listScans(50, 0), listSessions(50, 0)])
      .then(([scanData, sessionData]) => {
        setScans(scanData.items);
        setTotalScansCount(scanData.total);
        setTotalSessionsCount(sessionData.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const latestPerProject = deduplicateBySession(scans);
  const totalViolations = latestPerProject.reduce((s, sc) => s + sc.total_violations, 0);
  const totalAutoFix = latestPerProject.reduce((s, sc) => s + sc.auto_fixable, 0);
  const totalAi = latestPerProject.reduce((s, sc) => s + sc.ai_candidate, 0);
  const totalManual = latestPerProject.reduce((s, sc) => s + sc.manual_review, 0);

  const recentScans = scans.slice(0, 10);

  return (
    <PageLayout>
      <PageHeader title="Dashboard" />
      <PageDashboard>
        <PageDashboardCount title="Projects" count={totalSessionsCount} />
        <PageDashboardCount title="Total Violations" count={totalViolations} />
        <PageDashboardCount title="Auto-Fixable" count={totalAutoFix} />
        <PageDashboardCount title="AI Candidates" count={totalAi} />
        <PageDashboardCount title="Manual Review" count={totalManual} />
        <PageDashboardCount title="Total Scans" count={totalScansCount} />

        <PageDashboardCard title="Recent Scans" width="xxl" height="md" to="/scans" linkText="View all">
          {loading ? (
            <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
          ) : recentScans.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No scans recorded yet.</div>
          ) : (
            <table className="pf-v6-c-table pf-m-compact pf-m-grid-md" role="grid">
              <thead>
                <tr role="row">
                  <th role="columnheader">Project</th>
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
                {recentScans.map((scan) => (
                  <tr
                    key={scan.scan_id}
                    role="row"
                    tabIndex={0}
                    onClick={() => navigate(`/scans/${scan.scan_id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/scans/${scan.scan_id}`); } }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td role="cell" style={{ fontFamily: 'var(--pf-t--global--font--family--mono)' }}>
                      {scan.project_path}
                    </td>
                    <td role="cell">
                      <span className={`apme-badge ${scan.scan_type === 'fix' ? 'passed' : 'running'}`}>
                        {scan.scan_type}
                      </span>
                    </td>
                    <td role="cell">
                      <StatusBadge violations={scan.total_violations} scanType={scan.scan_type} />
                    </td>
                    <td role="cell">{scan.total_violations}</td>
                    <td role="cell"><span className="apme-count-success">{scan.auto_fixable ?? ''}</span></td>
                    <td role="cell">{scan.ai_candidate ?? ''}</td>
                    <td role="cell"><span className="apme-count-error">{scan.manual_review ?? ''}</span></td>
                    <td role="cell" style={{ opacity: 0.7 }}>{timeAgo(scan.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </PageDashboardCard>
      </PageDashboard>
    </PageLayout>
  );
}
