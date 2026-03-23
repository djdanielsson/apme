import { PageMasthead, PageThemeSwitcher, PageNotificationsIcon } from '@ansible/ansible-ui-framework';
import { PageMastheadDropdown } from '@ansible/ansible-ui-framework/PageMasthead/PageMastheadDropdown';
import {
  DropdownItem,
  ToolbarGroup,
  ToolbarItem,
} from '@patternfly/react-core';
import { QuestionCircleIcon } from '@patternfly/react-icons';

export function ApmeMasthead() {
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
              onClick={() => {
                /* TODO: about modal */
              }}
            >
              About APME
            </DropdownItem>
          </PageMastheadDropdown>
        </ToolbarItem>
      </ToolbarGroup>
    </PageMasthead>
  );
}
