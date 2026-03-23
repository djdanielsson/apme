import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getSession, getSessionTrend } from "../services/api";
import type { SessionDetail, TrendPoint } from "../types/api";
import { StatusBadge } from "../components/StatusBadge";
import { timeAgo } from "../services/format";

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

  if (loading) return <div className="apme-empty">Loading...</div>;
  if (!session) return <div className="apme-empty">Session not found.</div>;

  return (
    <>
      <nav className="apme-breadcrumb">
        <Link to="/sessions">Sessions</Link>
        <span className="apme-breadcrumb-sep">/</span>
        <span>{session.project_path}</span>
      </nav>

      <header className="apme-page-header">
        <div>
          <h1 className="apme-page-title" style={{ fontFamily: "var(--pf-v5-global--FontFamily--monospace, monospace)" }}>
            {session.project_path}
          </h1>
          <p style={{ color: "var(--apme-text-muted)", fontSize: 14, margin: 0 }}>
            Session {session.session_id} &middot; First seen {timeAgo(session.first_seen)} &middot; Last seen {timeAgo(session.last_seen)}
          </p>
        </div>
      </header>

      {/* Trend */}
      {trend.length > 0 && (
        <div className="apme-table-container" style={{ marginBottom: 24 }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--apme-border)" }}>
            <span style={{ fontSize: 16, fontWeight: 600 }}>Violation Trend</span>
          </div>
          <table className="apme-data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Total Violations</th>
                <th>Auto-Fixable</th>
              </tr>
            </thead>
            <tbody>
              {trend.map((pt) => (
                <tr
                  key={pt.scan_id}
                  onClick={() => navigate(`/scans/${pt.scan_id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td className="apme-time-ago">{new Date(pt.created_at).toLocaleString()}</td>
                  <td>
                    <span className={`apme-badge ${pt.scan_type === "fix" ? "passed" : "running"}`}>{pt.scan_type}</span>
                  </td>
                  <td>{pt.total_violations}</td>
                  <td>{pt.auto_fixable}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Scans for this session */}
      <div className="apme-table-container">
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--apme-border)" }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>Scans ({session.scans.length})</span>
        </div>
        {session.scans.length === 0 ? (
          <div className="apme-empty">No scans in this session.</div>
        ) : (
          <table className="apme-data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Violations</th>
                <th>Auto-Fix</th>
                <th>AI</th>
                <th>Manual</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {session.scans.map((scan) => (
                <tr key={scan.scan_id} onClick={() => navigate(`/scans/${scan.scan_id}`)} style={{ cursor: "pointer" }}>
                  <td>
                    <span className={`apme-badge ${scan.scan_type === "fix" ? "passed" : "running"}`}>{scan.scan_type}</span>
                  </td>
                  <td><StatusBadge violations={scan.total_violations} scanType={scan.scan_type} /></td>
                  <td>{scan.total_violations}</td>
                  <td><span className="apme-count-success">{scan.auto_fixable ?? ""}</span></td>
                  <td>{scan.ai_candidate ?? ""}</td>
                  <td><span className="apme-count-error">{scan.manual_review ?? ""}</span></td>
                  <td className="apme-time-ago">{timeAgo(scan.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
