import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import { getSession, getSessionTrend } from '../services/api';
import type { SessionDetail, TrendPoint } from '../types/api';
import { StatusBadge } from '../components/StatusBadge';
import { timeAgo } from '../services/format';

export function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId) return;
    setLoading(true);
    Promise.all([getSession(sessionId), getSessionTrend(sessionId).catch(() => [] as TrendPoint[])])
      .then(([s, t]) => { setSession(s); setTrend(t); })
      .catch(() => setSession(null))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <PageLayout><div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div></PageLayout>;
  if (!session) return <PageLayout><div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Session not found.</div></PageLayout>;

  return (
    <PageLayout>
      <PageHeader
        title={session.project_path}
        breadcrumbs={[
          { label: 'Sessions', to: '/sessions' },
          { label: session.project_path },
        ]}
        description={`Session ${session.session_id} \u00b7 First seen ${timeAgo(session.first_seen)} \u00b7 Last seen ${timeAgo(session.last_seen)}`}
      />

      <div style={{ padding: '0 24px 24px' }}>
        {/* Trend */}
        {trend.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h3 style={{ marginBottom: 12 }}>Violation Trend</h3>
            <table className="pf-v6-c-table pf-m-compact" role="grid">
              <thead>
                <tr role="row">
                  <th role="columnheader">Time</th>
                  <th role="columnheader">Type</th>
                  <th role="columnheader">Total Violations</th>
                  <th role="columnheader">Auto-Fixable</th>
                </tr>
              </thead>
              <tbody>
                {trend.map((pt) => (
                  <tr
                    key={pt.scan_id}
                    role="row"
                    tabIndex={0}
                    onClick={() => navigate(`/scans/${pt.scan_id}`)}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/scans/${pt.scan_id}`); } }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td role="cell" style={{ opacity: 0.7 }}>{new Date(pt.created_at).toLocaleString()}</td>
                    <td role="cell">
                      <span className={`apme-badge ${pt.scan_type === 'fix' ? 'passed' : 'running'}`}>{pt.scan_type}</span>
                    </td>
                    <td role="cell">{pt.total_violations}</td>
                    <td role="cell">{pt.auto_fixable}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Scans for this session */}
        <h3 style={{ marginBottom: 12 }}>Scans ({session.scans.length})</h3>
        {session.scans.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', opacity: 0.6 }}>No scans in this session.</div>
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
              {session.scans.map((scan) => (
                <tr
                  key={scan.scan_id}
                  role="row"
                  tabIndex={0}
                  onClick={() => navigate(`/scans/${scan.scan_id}`)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/scans/${scan.scan_id}`); } }}
                  style={{ cursor: 'pointer' }}
                >
                  <td role="cell">
                    <span className={`apme-badge ${scan.scan_type === 'fix' ? 'passed' : 'running'}`}>{scan.scan_type}</span>
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
      </div>
    </PageLayout>
  );
}
