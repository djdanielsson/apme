import { useEffect, useState } from 'react';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import { getAiAcceptance } from '../services/api';
import type { AiAcceptanceEntry } from '../types/api';

export function AiMetricsPage() {
  const [data, setData] = useState<AiAcceptanceEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAiAcceptance()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageLayout>
      <PageHeader
        title="AI Metrics"
        description="Proposal acceptance rates by rule"
      />

      {loading ? (
        <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
      ) : data.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>
          No AI proposal data yet. Run a fix session with AI escalation to see results.
        </div>
      ) : (
        <div style={{ padding: '0 24px 24px' }}>
          <table className="pf-v6-c-table pf-m-compact" role="grid">
            <thead>
              <tr role="row">
                <th role="columnheader">Rule</th>
                <th role="columnheader">Approved</th>
                <th role="columnheader">Rejected</th>
                <th role="columnheader">Pending</th>
                <th role="columnheader">Avg Confidence</th>
                <th role="columnheader">Acceptance Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => {
                const total = entry.approved + entry.rejected + entry.pending;
                const rate = total > 0 ? Math.round((entry.approved / total) * 100) : 0;
                return (
                  <tr key={entry.rule_id} role="row">
                    <td role="cell" className="apme-rule-id">{entry.rule_id}</td>
                    <td role="cell">
                      <span style={{ color: 'var(--pf-t--global--color--status--success--default)', fontWeight: 600 }}>{entry.approved}</span>
                    </td>
                    <td role="cell">
                      <span style={{ color: 'var(--pf-t--global--color--status--danger--default)', fontWeight: 600 }}>{entry.rejected}</span>
                    </td>
                    <td role="cell">{entry.pending}</td>
                    <td role="cell">{(entry.avg_confidence * 100).toFixed(0)}%</td>
                    <td role="cell">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ flex: 1, background: 'var(--pf-t--global--background--color--secondary--default)', borderRadius: 4, height: 16, maxWidth: 120 }}>
                          <div style={{
                            width: `${rate}%`,
                            background: rate > 70
                              ? 'var(--pf-t--global--color--status--success--default)'
                              : rate > 40
                                ? 'var(--pf-t--global--color--status--warning--default)'
                                : 'var(--pf-t--global--color--status--danger--default)',
                            height: '100%',
                            borderRadius: 4,
                          }} />
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{rate}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
