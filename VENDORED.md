# Vendored Dependencies

## `@ansible/ansible-ui-framework`

**Location:** `frontend/vendor/ansible-ui-framework/`

**Source:** `ansible/ansible-ui` — `framework/` directory

**Why vendored:** The upstream repository is private. Vendoring avoids git
submodule complexity in CI (deploy keys, token forwarding) and gives us full
control over patches.

### Patches applied

1. **`PageApp/PageApp.tsx`** — Removed the `ChatbotSideBar` import and wrapper
   (APME does not use the `@ansible/chatbot` package).
2. **`index.ts`** — Trimmed to re-export only the modules APME actually
   consumes. This prevents Rollup from trying to resolve unused heavy
   dependencies like `monaco-editor`.
3. **`tsconfig.json`** — Replaced `"extends": "../tsconfig.json"` with a
   standalone, relaxed configuration so the vendored code builds inside the
   APME frontend tree.

### Exports used by APME

The trimmed `index.ts` exports only:

- `PageApp`, `PageFramework`, `PageLayout`, `PageHeader`, `PageBody`
- `PageMasthead`, `PageThemeSwitcher`, `PageNotificationsIcon`
- `PageNavigation`, `PageNavigationItem`, `PageNavSidebar`
- `PageDashboard`, `PageDashboardCard`, `PageDashboardCount`
- `PageNotificationsDrawer`, `usePageNotifications`
- `PageSettingsProvider`, `PageTabs`
- `PageNotFound`, `LoadingPage`, `Scrollable`, `useBreakpoint`
- `useFrameworkTranslations`, `useGetPageUrl`, `usePageNavigate`

### How to update

```bash
# From the repo root, with a fresh clone of aap-ui alongside:
rsync -av --delete \
  --exclude node_modules \
  --exclude dist \
  --exclude .git \
  ../aap-ui/framework/ frontend/vendor/ansible-ui-framework/

# Re-apply patches:
# 1. Remove ChatbotSideBar from PageApp/PageApp.tsx
# 2. Restore the trimmed index.ts (keep only APME-used exports)
# 3. Restore the standalone tsconfig.json

# Verify:
cd frontend && npm run build && npx vitest run
```

### Peer dependencies

The framework expects these as peers (installed in `frontend/package.json`):

- `@patternfly/react-core` 6.x
- `@patternfly/react-icons` 6.x
- `@patternfly/patternfly` 6.x
- `react` 18.x, `react-dom` 18.x, `react-router-dom` 6.x
- `swr`, `react-i18next`, `i18next`, `styled-components`
- `@react-hook/resize-observer`
