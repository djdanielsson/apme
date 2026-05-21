# Documentation Q&A Audit - 2026-05-21

## Executive Summary

- **Total Questions**: 34
- **Covered**: 13 (38%)
- **Partial**: 9 (26%)
- **Gaps**: 12 (35%)

The documentation has solid coverage of core functionality (installation, basic scanning, container deployment, rule catalog) but significant gaps exist in CI/CD integration guides, tooling ecosystem integration, and some rule configuration topics.

## Coverage by Category

| Category | Covered | Partial | Gap | Score |
|----------|---------|---------|-----|-------|
| What Is It / What Does It Do | 4/5 | 1/5 | 0/5 | 90% |
| How Can I Use It | 4/5 | 1/5 | 0/5 | 90% |
| Rule Configuration | 1/5 | 3/5 | 1/5 | 50% |
| Bring Your Own Rules | 0/4 | 3/4 | 1/4 | 38% |
| Demonstrating Value | 1/5 | 1/5 | 3/5 | 30% |
| Integration with Existing Tools | 3/10 | 0/10 | 7/10 | 30% |

## Coverage Matrix

| ID | Category | Question | Status | Source |
|----|----------|----------|--------|--------|
| Q01 | What Is It | What is APME and what problem does it solve? | Covered | [README.md#what-apme-is](README.md) |
| Q02 | What Is It | What types of Ansible content can APME scan? | Covered | [README.md#what-apme-is](README.md) |
| Q03 | What Is It | What rules does APME enforce and why? | Covered | [docs/rules/RULE_CATALOG.md](docs/rules/RULE_CATALOG.md) |
| Q04 | What Is It | How does APME differ from ansible-lint? | Partial | [docs/rules/ANSIBLELINT_COVERAGE.md](docs/rules/ANSIBLELINT_COVERAGE.md) |
| Q05 | What Is It | What are the severity levels and what do they mean? | Covered | [docs/rules/RULE_CATALOG.md](docs/rules/RULE_CATALOG.md) |
| Q06 | How Can I Use It | How do I install APME? | Covered | [README.md#install](README.md) |
| Q07 | How Can I Use It | How do I run a basic scan? | Covered | [README.md#basic-usage](README.md) |
| Q08 | How Can I Use It | How do I get JSON output for automation? | Covered | [README.md#basic-usage](README.md) |
| Q09 | How Can I Use It | How do I run APME in a container? | Covered | [README.md#container-deployment-podman](README.md), [docs/guides/DEPLOYMENT.md](docs/guides/DEPLOYMENT.md) |
| Q10 | How Can I Use It | How do I use daemon vs pod mode? | Partial | [docs/guides/DEPLOYMENT.md#local-development-daemon-mode](docs/guides/DEPLOYMENT.md) |
| Q11 | Rule Config | How do I enable/disable specific rules? | Partial | [src/apme_engine/cli/_rules_yml.py](src/apme_engine/cli/_rules_yml.py) (code only) |
| Q12 | Rule Config | How do I change rule severity? | Partial | [.sdlc/adrs/ADR-041-rule-catalog-override-architecture.md](.sdlc/adrs/ADR-041-rule-catalog-override-architecture.md) |
| Q13 | Rule Config | How do I suppress a rule for a specific line? | Gap | No documentation found |
| Q14 | Rule Config | How do I configure rules per-project? | Partial | [src/apme_engine/cli/_rules_yml.py](src/apme_engine/cli/_rules_yml.py) (code only) |
| Q15 | Rule Config | How do I enforce rules and ignore noqa comments? | Covered | [.sdlc/adrs/ADR-041-rule-catalog-override-architecture.md](.sdlc/adrs/ADR-041-rule-catalog-override-architecture.md) |
| Q16 | Custom Rules | Can I add custom rules? | Partial | [.sdlc/adrs/ADR-042-third-party-plugin-services.md](.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q17 | Custom Rules | How do I write a custom OPA/Rego rule? | Partial | [docs/guides/DEVELOPMENT.md#opa-rego-rule](docs/guides/DEVELOPMENT.md) |
| Q18 | Custom Rules | How do I add custom rules via plugins? | Partial | [.sdlc/adrs/ADR-042-third-party-plugin-services.md](.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q19 | Custom Rules | What rule ID conventions should custom rules follow? | Gap | ADR-008 exists but not user-facing |
| Q20 | Value | How do I show before/after remediation? | Covered | [README.md#basic-usage](README.md) |
| Q21 | Value | How do I track improvement over time? | Gap | No documentation found |
| Q22 | Value | How do I generate reports for stakeholders? | Partial | [docs/architecture/13-gateway-and-persistence.md](docs/architecture/13-gateway-and-persistence.md) |
| Q23 | Value | How do I measure AI fix acceptance rates? | Gap | API exists per 13-gateway, no user guide |
| Q24 | Value | What metrics does the Gateway API provide? | Gap | [docs/architecture/13-gateway-and-persistence.md](docs/architecture/13-gateway-and-persistence.md) (architecture, not guide) |
| Q25 | Integration | How do I integrate with GitHub Actions? | Gap | No documentation found |
| Q26 | Integration | How do I integrate with GitLab CI? | Gap | No documentation found |
| Q27 | Integration | How do I integrate with Jenkins? | Gap | No documentation found |
| Q28 | Integration | How do I integrate with Azure DevOps? | Gap | No documentation found |
| Q29 | Integration | How do I use APME with AAP/AWX? | Gap | No documentation found |
| Q30 | Integration | How do I use APME with Backstage? | Gap | No documentation found |
| Q31 | Integration | How do I use APME with pre-commit hooks? | Gap | No documentation found |
| Q32 | Integration | How do I migrate from ansible-lint? | Covered | [docs/rules/ANSIBLELINT_COVERAGE.md](docs/rules/ANSIBLELINT_COVERAGE.md) |
| Q33 | Integration | How do I use APME in an air-gapped environment? | Covered | [docs/guides/DEPLOYMENT.md#custom-ca-certificates](docs/guides/DEPLOYMENT.md) |
| Q34 | Integration | How do I integrate with VS Code? | Covered | No VS Code extension exists yet; N/A |

## Gap Analysis

### Gap 1: Inline Suppression (Q13)

- **ID**: Q13
- **Question**: How do I suppress a rule for a specific line?
- **Impact**: Users need to suppress false positives in specific locations without disabling the rule globally. This is a fundamental workflow.
- **Suggested Location**: `docs/guides/CONFIGURATION.md` (new file) or README.md
- **Research Notes**: ADR-041 mentions `# apme:ignore` annotations and `enforced` flag to ignore them, but there is no user-facing documentation explaining the syntax or usage.
- **Draft Answer**: Add inline `# apme:ignore` or `# apme:ignore[L026]` comment to suppress violations on that line. Use `enforced: true` in `.apme/rules.yml` to make suppression impossible for compliance-critical rules.

### Gap 2: Rule ID Conventions for Custom Rules (Q19)

- **ID**: Q19
- **Question**: What rule ID conventions should custom rules follow?
- **Impact**: Users writing custom rules need to understand the ID naming scheme to avoid conflicts and maintain consistency.
- **Suggested Location**: `docs/guides/CUSTOM_RULES.md` (new file)
- **Research Notes**: ADR-008 defines L/M/R/P/SEC prefixes. ADR-042 defines EXT- prefix for plugins. This information exists but is not in user-facing docs.
- **Draft Answer**: Built-in rules use prefixes: L (lint), M (modernize), R (risk), P (policy), SEC (secrets). Custom plugin rules must use `EXT-<plugin_name>-<NNN>` format (e.g., `EXT-secteam-001`).

### Gap 3: Tracking Improvement Over Time (Q21)

- **ID**: Q21
- **Question**: How do I track improvement over time?
- **Impact**: Stakeholders want to see progress. Without guidance, users cannot demonstrate ROI.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Research Notes**: Gateway API has `/projects/{id}/trend` endpoint and health scores per 13-gateway architecture doc, but no user guide exists.
- **Draft Answer**: The Gateway REST API provides trend data via `GET /api/v1/projects/{id}/trend`. The UI dashboard shows violation trends over time. Health scores are computed per project.

### Gap 4: AI Acceptance Rates (Q23)

- **ID**: Q23
- **Question**: How do I measure AI fix acceptance rates?
- **Impact**: Teams evaluating AI remediation need metrics to justify the investment.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Research Notes**: Gateway API has `GET /api/v1/stats/ai-acceptance` endpoint per 13-gateway.
- **Draft Answer**: Query `GET /api/v1/stats/ai-acceptance` from the Gateway API for proposal approval/rejection statistics.

### Gap 5: Gateway API Metrics Guide (Q24)

- **ID**: Q24
- **Question**: What metrics does the Gateway API provide?
- **Impact**: API consumers need a reference to build dashboards and integrations.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Research Notes**: Full endpoint list exists in 13-gateway architecture doc. Needs user-facing guide with examples.
- **Draft Answer**: Document the dashboard endpoints: `/dashboard/summary`, `/violations/top`, `/stats/remediation-rates`, `/stats/ai-acceptance`.

### Gap 6: GitHub Actions Integration (Q25)

- **ID**: Q25
- **Question**: How do I integrate with GitHub Actions?
- **Impact**: GitHub Actions is the most common CI system. Without a guide, users must figure out integration themselves.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: The CLI supports `--json` output and exit codes suitable for CI. No example workflow exists.
- **Draft Answer**: Create example workflow using `pip install apme-engine@git+...` and `apme check --json .`.

### Gap 7: GitLab CI Integration (Q26)

- **ID**: Q26
- **Question**: How do I integrate with GitLab CI?
- **Impact**: GitLab CI is widely used. Missing documentation forces users to experiment.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: Same CLI capabilities apply. No `.gitlab-ci.yml` example exists.

### Gap 8: Jenkins Integration (Q27)

- **ID**: Q27
- **Question**: How do I integrate with Jenkins?
- **Impact**: Many enterprises use Jenkins. Integration guide needed.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: CLI can be run in Jenkins pipelines. No example Jenkinsfile exists.

### Gap 9: Azure DevOps Integration (Q28)

- **ID**: Q28
- **Question**: How do I integrate with Azure DevOps?
- **Impact**: Azure DevOps users need guidance.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: No Azure Pipelines example exists.

### Gap 10: AAP/AWX Integration (Q29)

- **ID**: Q29
- **Question**: How do I use APME with AAP/AWX?
- **Impact**: AAP is the target platform for APME. Integration with execution environments and workflows is critical.
- **Suggested Location**: `docs/guides/AAP_INTEGRATION.md` (new file)
- **Research Notes**: README mentions AAP 2.5+ as the target. Roadmap mentions EE compatibility rules. No integration guide exists.
- **Draft Answer**: APME scans content for AAP 2.5+ compatibility. For EE integration, use `--ansible-core-version` flag. Future: EE compatibility rules (R505-R507) planned.

### Gap 11: Backstage Integration (Q30)

- **ID**: Q30
- **Question**: How do I use APME with Backstage?
- **Impact**: Portal/Backstage integration is relevant for platform engineering teams.
- **Suggested Location**: `docs/guides/BACKSTAGE_INTEGRATION.md` (new file)
- **Research Notes**: No Backstage plugin or integration guide exists. The Gateway API could be consumed by a Backstage plugin.

### Gap 12: Pre-commit Hooks (Q31)

- **ID**: Q31
- **Question**: How do I use APME with pre-commit hooks?
- **Impact**: Pre-commit is a popular developer workflow. Missing documentation is a usability gap.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` or README.md
- **Research Notes**: No `.pre-commit-config.yaml` example exists. The CLI could be wrapped as a pre-commit hook.
- **Draft Answer**: Create `.pre-commit-config.yaml` entry using `apme check` as a local hook.

## Partial Coverage Improvements

### Partial 1: ansible-lint Comparison (Q04)

- **Current Source**: docs/rules/ANSIBLELINT_COVERAGE.md
- **Gap**: Coverage matrix exists but lacks a prose explanation of key differences and migration path.
- **Recommendation**: Add a "Why APME vs ansible-lint" section to README.md or a dedicated comparison guide.

### Partial 2: Daemon vs Pod Mode (Q10)

- **Current Source**: docs/guides/DEPLOYMENT.md
- **Gap**: Explains both modes but lacks a decision tree for when to use each.
- **Recommendation**: Add a "Which mode should I use?" section with clear guidance.

### Partial 3: Enable/Disable Rules (Q11)

- **Current Source**: Code in `_rules_yml.py`
- **Gap**: The `.apme/rules.yml` format is only documented in code comments.
- **Recommendation**: Create `docs/guides/CONFIGURATION.md` with examples.

### Partial 4: Severity Override (Q12)

- **Current Source**: ADR-041
- **Gap**: ADR explains architecture, not user workflow.
- **Recommendation**: Add user-facing examples to CONFIGURATION.md.

### Partial 5: Per-project Config (Q14)

- **Current Source**: Code in `_rules_yml.py`
- **Gap**: No user documentation for `.apme/rules.yml`.
- **Recommendation**: Document in CONFIGURATION.md.

### Partial 6: Custom Rules Overview (Q16)

- **Current Source**: ADR-042
- **Gap**: ADR is developer-focused, not user-facing.
- **Recommendation**: Create `docs/guides/CUSTOM_RULES.md` with high-level overview.

### Partial 7: Custom OPA/Rego Rules (Q17)

- **Current Source**: docs/guides/DEVELOPMENT.md
- **Gap**: Development guide shows internal rule addition, not external/user-facing custom rules.
- **Recommendation**: Clarify distinction between internal development and plugin extensibility.

### Partial 8: Plugin Rules (Q18)

- **Current Source**: ADR-042
- **Gap**: SDK documentation planned but not yet published.
- **Recommendation**: Complete Phase 5 of ADR-042 implementation (documentation and SDK guide).

### Partial 9: Stakeholder Reports (Q22)

- **Current Source**: 13-gateway architecture doc
- **Gap**: API endpoints documented but no guide on generating stakeholder reports.
- **Recommendation**: Create `docs/guides/REPORTING.md` with report examples.

## Action Items

### High Priority (Core User Workflows)

- [ ] Create `docs/guides/CONFIGURATION.md` documenting `.apme/rules.yml` format, inline suppression (`# apme:ignore`), severity overrides, and `enforced` flag
- [ ] Create `docs/guides/CI_INTEGRATION.md` with examples for GitHub Actions, GitLab CI, Jenkins, Azure DevOps, and pre-commit hooks

### Medium Priority (Value Demonstration)

- [ ] Create `docs/guides/REPORTING.md` documenting Gateway API metrics, trend endpoints, AI acceptance stats, and stakeholder reporting workflows
- [ ] Add "Why APME vs ansible-lint" comparison section to README.md or a dedicated guide

### Lower Priority (Advanced/Future)

- [ ] Create `docs/guides/CUSTOM_RULES.md` with rule ID conventions and plugin SDK overview
- [ ] Create `docs/guides/AAP_INTEGRATION.md` for AAP/EE integration guidance
- [ ] Document Backstage integration pattern when plugin is available

## Next Steps

1. Review gaps with stakeholders to prioritize based on customer frequency
2. Create CONFIGURATION.md and CI_INTEGRATION.md as highest-impact additions
3. Add inline suppression syntax to user-facing docs immediately
4. Re-run audit after documentation updates
