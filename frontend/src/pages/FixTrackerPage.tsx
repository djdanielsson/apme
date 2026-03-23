import { useEffect, useState } from "react";
import { getFixRates } from "../services/api";
import type { FixRateEntry } from "../types/api";
import { getRuleDescription } from "../data/ruleDescriptions";

export function FixTrackerPage() {
  const [data, setData] = useState<FixRateEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getFixRates(30)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const maxCount = data.length > 0 ? data[0]!.fix_count : 1;

  return (
    <>
      <header className="apme-page-header">
        <div>
          <h1 className="apme-page-title">Fix Tracker</h1>
          <p style={{ color: "var(--apme-text-muted)", margin: 0, fontSize: 14 }}>
            Most frequently addressed rules in fix sessions
          </p>
        </div>
      </header>

      {loading ? (
        <div className="apme-empty">Loading...</div>
      ) : data.length === 0 ? (
        <div className="apme-empty">No fix data yet. Run a fix session to see results.</div>
      ) : (
        <div className="apme-table-container">
          <table className="apme-data-table">
            <thead>
              <tr>
                <th style={{ width: 90 }}>Rule</th>
                <th>Description</th>
                <th style={{ width: "35%" }}></th>
                <th style={{ width: 60, textAlign: "right" }}>Fixes</th>
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
                        width: `${(entry.fix_count / maxCount) * 100}%`,
                        background: "var(--apme-green)",
                        height: "100%",
                        borderRadius: 4,
                        minWidth: 2,
                      }} />
                    </div>
                  </td>
                  <td style={{ textAlign: "right", fontSize: 13, fontWeight: 600, color: "var(--apme-text-secondary)" }}>
                    {entry.fix_count}
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
