import { Tooltip } from '@patternfly/react-core';
import { getRuleDescription } from '../data/ruleDescriptions';
import { bareRuleId } from './severity';

function SingleRuleId({ ruleId, className }: { ruleId: string; className?: string }) {
  const desc = getRuleDescription(ruleId);
  const bare = bareRuleId(ruleId);
  const spanClassName = className ?? 'apme-rule-id';

  if (!desc) {
    return <span className={spanClassName}>{bare}</span>;
  }

  return (
    <Tooltip content={desc}>
      <span className={spanClassName} tabIndex={0}>
        {bare}
      </span>
    </Tooltip>
  );
}

export function RuleId({ ruleId, className }: { ruleId: string; className?: string }) {
  const ids = ruleId.split(',').map((s) => s.trim()).filter(Boolean);
  if (ids.length <= 1) {
    return <SingleRuleId ruleId={ruleId} className={className} />;
  }
  return (
    <>
      {ids.map((id, i) => (
        <span key={`${id}-${i}`}>
          {i > 0 && ','}
          <SingleRuleId ruleId={id} className={className} />
        </span>
      ))}
    </>
  );
}
