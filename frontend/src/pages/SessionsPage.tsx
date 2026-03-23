import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions } from "../services/api";
import type { SessionSummary } from "../types/api";
import { timeAgo } from "../services/format";

const PAGE_SIZE = 20;

export function SessionsPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listSessions(PAGE_SIZE, offset)
      .then((data) => {
        setSessions(data.items);
        setTotal(data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [offset]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <>
      <header className="apme-page-header">
        <h1 className="apme-page-title">Sessions</h1>
      </header>

      {loading ? (
        <div className="apme-empty">Loading...</div>
      ) : sessions.length === 0 ? (
        <div className="apme-empty">No sessions recorded.</div>
      ) : (
        <div className="apme-table-container">
          <table className="apme-data-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Session ID</th>
                <th>First Seen</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id} onClick={() => navigate(`/sessions/${s.session_id}`)} style={{ cursor: "pointer" }}>
                  <td className="apme-target-path">{s.project_path}</td>
                  <td style={{ fontFamily: "var(--pf-v5-global--FontFamily--monospace, monospace)", fontSize: 13 }}>
                    {s.session_id}
                  </td>
                  <td className="apme-time-ago">{timeAgo(s.first_seen)}</td>
                  <td className="apme-time-ago">{timeAgo(s.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="apme-pagination">
              <button className="apme-btn apme-btn-secondary" disabled={offset <= 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </button>
              <span>Page {currentPage} of {totalPages}</span>
              <button className="apme-btn apme-btn-secondary" disabled={currentPage >= totalPages} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
