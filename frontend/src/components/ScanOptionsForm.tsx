import {
  Checkbox,
  ExpandableSection,
  Flex,
  FlexItem,
  TextInput,
} from '@patternfly/react-core';

export interface ScanOptionsFormProps {
  ansibleVersion: string;
  onAnsibleVersionChange: (value: string) => void;
  collections: string;
  onCollectionsChange: (value: string) => void;
  enableAi: boolean;
  onEnableAiChange: (checked: boolean) => void;
  idPrefix?: string;
}

export function ScanOptionsForm({
  ansibleVersion,
  onAnsibleVersionChange,
  collections,
  onCollectionsChange,
  enableAi,
  onEnableAiChange,
  idPrefix = '',
}: ScanOptionsFormProps) {
  const prefix = idPrefix ? `${idPrefix}-` : '';

  return (
    <ExpandableSection toggleText="Advanced Options" style={{ marginTop: 8 }}>
      <Flex direction={{ default: 'column' }} gap={{ default: 'gapMd' }}>
        <FlexItem>
          <label htmlFor={`${prefix}ansible-version`} style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>
            Ansible Core Version
          </label>
          <TextInput
            id={`${prefix}ansible-version`}
            placeholder="e.g. 2.16"
            value={ansibleVersion}
            onChange={(_e, v) => onAnsibleVersionChange(v)}
          />
        </FlexItem>
        <FlexItem>
          <label htmlFor={`${prefix}collections`} style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>
            Collections (comma-separated)
          </label>
          <TextInput
            id={`${prefix}collections`}
            placeholder="e.g. ansible.posix, community.general"
            value={collections}
            onChange={(_e, v) => onCollectionsChange(v)}
          />
        </FlexItem>
        <FlexItem>
          <Checkbox
            id={`${prefix}enable-ai`}
            label="Enable AI-assisted remediation (Tier 2)"
            isChecked={enableAi}
            onChange={(_e, checked) => onEnableAiChange(checked)}
          />
        </FlexItem>
      </Flex>
    </ExpandableSection>
  );
}
