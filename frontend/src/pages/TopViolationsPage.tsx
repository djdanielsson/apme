import { useEffect, useState } from 'react';
import { PageLayout, PageHeader } from '@ansible/ansible-ui-framework';
import { getTopViolations } from '../services/api';
import type { TopViolation } from '../types/api';
import { getRuleDescription } from '../data/ruleDescriptions';

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
    <PageLayout>
      <PageHeader title="Top Violations" />

      {loading ? (
        <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>Loading...</div>
      ) : data.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', opacity: 0.6 }}>No violation data yet.</div>
      ) : (
        <div style={{ padding: '0 24px 24px' }}>
          <table className="pf-v6-c-table pf-m-compact" role="grid">
            <thead>
              <tr role="row">
                <th role="columnheader" style={{ width: 90 }}>Rule</th>
                <th role="columnheader">Description</th>
                <th role="columnheader" style={{ width: '35%' }}></th>
                <th role="columnheader" style={{ width: 60, textAlign: 'right' }}>Count</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry) => (
                <tr key={entry.rule_id} role="row" title={getRuleDescription(entry.rule_id) || entry.rule_id}>
                  <td role="cell">
                    <span className="apme-rule-id">{entry.rule_id}</span>
                  </td>
                  <td role="cell" style={{ fontSize: 13, opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 300 }}>
                    {getRuleDescription(entry.rule_id)}
                  </td>
                  <td role="cell">
                    <div style={{ background: 'var(--pf-t--global--background--color--secondary--default)', borderRadius: 4, height: 16 }}>
                      <div style={{
                        width: `${(entry.count / maxCount) * 100}%`,
                        background: 'var(--pf-t--global--color--brand--default)',
                        height: '100%',
                        borderRadius: 4,
                        minWidth: 2,
                      }} />
                    </div>
                  </td>
                  <td role="cell" style={{ textAlign: 'right', fontSize: 13, fontWeight: 600 }}>
                    {entry.count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
