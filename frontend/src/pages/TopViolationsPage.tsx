import { useEffect, useState } from "react";
import { getTopViolations } from "../services/api";
import type { TopViolation } from "../types/api";
import { getRuleDescription } from "../data/ruleDescriptions";

export function TopViolationsPage() {
  const [data, setData] = useState<TopViolation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTopViolations(30)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const maxCount = data.length > 0 ? data[0]!.count : 1;

  return (
    <>
      <header className="apme-page-header">
        <h1 className="apme-page-title">Top Violations</h1>
      </header>

      {loading ? (
        <div className="apme-empty">Loading...</div>
      ) : data.length === 0 ? (
        <div className="apme-empty">No violation data yet.</div>
      ) : (
        <div className="apme-table-container">
          <table className="apme-data-table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>Rule</th>
                <th>Description</th>
                <th style={{ width: "35%" }}></th>
                <th style={{ width: 60, textAlign: "right" }}>Count</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => (
                <tr key={entry.rule_id} title={getRuleDescription(entry.rule_id) || entry.rule_id}>
                  <td>
                    <span className="apme-rule-id">{entry.rule_id}</span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--apme-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 300 }}>
                    {getRuleDescription(entry.rule_id)}
                  </td>
                  <td>
                    <div style={{ background: "var(--apme-bg-tertiary)", borderRadius: 4, height: 16 }}>
                      <div style={{
                        width: `${(entry.count / maxCount) * 100}%`,
                        background: "var(--apme-accent)",
                        height: "100%",
                        borderRadius: 4,
                        minWidth: 2,
                      }} />
                    </div>
                  </td>
                  <td style={{ textAlign: "right", fontSize: 13, fontWeight: 600, color: "var(--apme-text-secondary)" }}>
                    {entry.count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
