import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PageFramework, PageApp } from '@ansible/ansible-ui-framework';
import { ApmeMasthead } from '../components/ApmeMasthead';
import { useApmeNavigation } from '../hooks/useApmeNavigation';

function TestApp() {
  const navigation = useApmeNavigation();
  return (
    <PageApp
      masthead={<ApmeMasthead />}
      navigation={navigation}
      defaultRefreshInterval={30}
    />
  );
}

function renderApp(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <PageFramework defaultRefreshInterval={30}>
        <TestApp />
      </PageFramework>
    </MemoryRouter>,
  );
}

describe('App Shell', () => {
  it('renders APME branding in the masthead', () => {
    renderApp();
    expect(screen.getByText('APME')).toBeInTheDocument();
  });

  it('renders sidebar navigation items', () => {
    renderApp();
    const nav = screen.getByTestId('page-navigation');
    expect(nav).toBeInTheDocument();

    for (const label of ['Dashboard', 'New Scan', 'Scans', 'Sessions', 'Top Violations', 'Fix Tracker', 'AI Metrics', 'Health']) {
      const items = screen.getAllByText(label);
      expect(items.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('renders the nav toggle button', () => {
    renderApp();
    expect(screen.getByTestId('nav-toggle')).toBeInTheDocument();
  });

  it('renders the theme switcher', () => {
    renderApp();
    const themeBtn = screen.queryByTestId('settings-icon') ?? screen.queryByTestId('theme-icon');
    expect(themeBtn).not.toBeNull();
  });

  it('renders the help menu dropdown toggle', () => {
    renderApp();
    expect(document.getElementById('help-menu-menu-toggle')).toBeInTheDocument();
  });
});
