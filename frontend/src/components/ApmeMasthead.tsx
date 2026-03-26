import { useState } from 'react';
import { PageMasthead, PageThemeSwitcher, PageNotificationsIcon } from '@ansible/ansible-ui-framework';
import { PageMastheadDropdown } from '@ansible/ansible-ui-framework/PageMasthead/PageMastheadDropdown';
import {
  AboutModal,
  Content,
  DropdownItem,
  ToolbarGroup,
  ToolbarItem,
} from '@patternfly/react-core';
import { QuestionCircleIcon } from '@patternfly/react-icons';

export function ApmeMasthead() {
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <PageMasthead
      brand={
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: 1.5 }}>
          APME
        </span>
      }
    >
      <ToolbarItem style={{ flexGrow: 1 }} />
      <ToolbarGroup variant="action-group-plain">
        <ToolbarItem visibility={{ default: 'hidden', lg: 'visible' }}>
          <PageThemeSwitcher />
        </ToolbarItem>
        <ToolbarItem>
          <PageNotificationsIcon />
        </ToolbarItem>
        <ToolbarItem>
          <PageMastheadDropdown id="help-menu" icon={<QuestionCircleIcon />}>
            <DropdownItem
              id="docs"
              isExternalLink
              component="a"
              href="https://github.com/ansible/apme"
            >
              Documentation
            </DropdownItem>
            <DropdownItem
              id="about"
              onClick={() => setAboutOpen(true)}
            >
              About APME
            </DropdownItem>
          </PageMastheadDropdown>
        </ToolbarItem>
      </ToolbarGroup>

      <AboutModal
        isOpen={aboutOpen}
        onClose={() => setAboutOpen(false)}
        trademark={`Copyright ${new Date().getFullYear()} Red Hat, Inc.`}
        brandImageSrc=""
        brandImageAlt="APME"
        productName="APME"
      >
        <Content>
          <Content component="dl">
            <Content component="dt">Version</Content>
            <Content component="dd">{__APME_VERSION__}</Content>
          </Content>
          <Content component="p" style={{ marginTop: 16, opacity: 0.7 }}>
            Ansible Policy &amp; Modernization Engine
          </Content>
        </Content>
      </AboutModal>
    </PageMasthead>
  );
}
