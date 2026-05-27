# Documentation Q&A Audit - 2026-05-21

## Executive Summary

- **Total Questions**: 34
- **Covered** (✓): 16 (47%)
- **Partial** (⚠): 9 (26%)
- **Gaps** (✗): 9 (26%)

The documentation has solid coverage of core functionality (installation, basic scanning, container deployment, rule catalog, and rule configuration) but significant gaps remain in CI/CD integration guides, tooling ecosystem integration, and higher-level reporting workflows.

## Coverage by Category

| Category | Covered | Partial | Gap | Score |
|----------|---------|---------|-----|-------|
| What Is It / What Does It Do | 4/5 | 1/5 | 0/5 | 90% |
| How Can I Use It | 4/5 | 1/5 | 0/5 | 90% |
| Rule Configuration | 4/5 | 1/5 | 0/5 | 90% |
| Bring Your Own Rules | 0/4 | 4/4 | 0/4 | 50% |
| Demonstrating Value | 2/5 | 2/5 | 1/5 | 60% |
| Integration with Existing Tools | 2/10 | 0/10 | 8/10 | 20% |

## Coverage Matrix

| ID | Category | Question | Status | Source |
|----|----------|----------|--------|--------|
| Q01 | What Is It / What Does It Do | What is APME and what problem does it solve? | ✓ | [README.md#what-apme-is](../../README.md#what-apme-is) |
| Q02 | What Is It / What Does It Do | What types of Ansible content can APME scan? | ✓ | [README.md#what-apme-is](../../README.md#what-apme-is) |
| Q03 | What Is It / What Does It Do | What rules does APME enforce and why? | ✓ | [RULE_CATALOG.md](../rules/RULE_CATALOG.md) |
| Q04 | What Is It / What Does It Do | How does APME differ from ansible-lint? | ⚠ | [ANSIBLELINT_COVERAGE.md](../rules/ANSIBLELINT_COVERAGE.md) |
| Q05 | What Is It / What Does It Do | What are the severity levels and what do they mean? | ✓ | [RULE_CATALOG.md](../rules/RULE_CATALOG.md) |
| Q06 | How Can I Use It | How do I install APME? | ✓ | [README.md#install](../../README.md#install) |
| Q07 | How Can I Use It | How do I run a basic scan? | ✓ | [README.md#basic-usage](../../README.md#basic-usage) |
| Q08 | How Can I Use It | How do I get JSON output for automation? | ✓ | [README.md#basic-usage](../../README.md#basic-usage) |
| Q09 | How Can I Use It | How do I run APME in a container? | ✓ | [README.md](../../README.md), [DEPLOYMENT.md](../guides/DEPLOYMENT.md) |
| Q10 | How Can I Use It | How do I use daemon vs pod mode? | ⚠ | [DEPLOYMENT.md#local-development-daemon-mode](../guides/DEPLOYMENT.md#local-development-daemon-mode) |
| Q11 | Rule Configuration | How do I enable/disable specific rules? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q12 | Rule Configuration | How do I change rule severity? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q13 | Rule Configuration | How do I suppress a rule for a specific line? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q14 | Rule Configuration | How do I configure rules per-project? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q15 | Rule Configuration | How do I enforce rules and ignore noqa comments? | ⚠ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md), [graph_scanner.py](../../src/apme_engine/engine/graph_scanner.py) |
| Q16 | Bring Your Own Rules | Can I add custom rules? | ⚠ | [ADR-042](../../.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q17 | Bring Your Own Rules | How do I write a custom OPA/Rego rule? | ⚠ | [DEVELOPMENT.md](../guides/DEVELOPMENT.md) |
| Q18 | Bring Your Own Rules | How do I add custom rules via plugins? | ⚠ | [ADR-042](../../.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q19 | Bring Your Own Rules | What rule ID conventions should custom rules follow? | ⚠ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q20 | Demonstrating Value | How do I show before/after remediation? | ✓ | [README.md#basic-usage](../../README.md#basic-usage) |
| Q21 | Demonstrating Value | How do I track improvement over time? | ✗ | No documentation found |
| Q22 | Demonstrating Value | How do I generate reports for stakeholders? | ⚠ | [13-gateway-and-persistence.md](../architecture/13-gateway-and-persistence.md) |
| Q23 | Demonstrating Value | How do I measure AI fix acceptance rates? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q24 | Demonstrating Value | What metrics does the Gateway API provide? | ⚠ | [13-gateway-and-persistence.md](../architecture/13-gateway-and-persistence.md) |
| Q25 | Integration with Existing Tools | How do I integrate with GitHub Actions? | ✗ | No documentation found |
| Q26 | Integration with Existing Tools | How do I integrate with GitLab CI? | ✗ | No documentation found |
| Q27 | Integration with Existing Tools | How do I integrate with Jenkins? | ✗ | No documentation found |
| Q28 | Integration with Existing Tools | How do I integrate with Azure DevOps? | ✗ | No documentation found |
| Q29 | Integration with Existing Tools | How do I use APME with AAP/AWX? | ✗ | No documentation found |
| Q30 | Integration with Existing Tools | How do I use APME with Backstage? | ✗ | No documentation found |
| Q31 | Integration with Existing Tools | How do I integrate with pre-commit hooks? | ✗ | No documentation found |
| Q32 | Integration with Existing Tools | How do I migrate from ansible-lint? | ✓ | [ANSIBLELINT_COVERAGE.md](../rules/ANSIBLELINT_COVERAGE.md) |
| Q33 | Integration with Existing Tools | How do I use APME in an air-gapped environment? | ✓ | [DEPLOYMENT.md#custom-ca-certificates](../guides/DEPLOYMENT.md#custom-ca-certificates) |
| Q34 | Integration with Existing Tools | How do I integrate with VS Code? | ✗ | No VS Code extension exists yet |

## Gap Analysis

### Gap 1: Tracking Improvement Over Time (Q21)

- **ID**: Q21
- **Question**: How do I track improvement over time?
- **Impact**: Stakeholders want to see progress. Without guidance, users cannot demonstrate ROI.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Research Notes**: Gateway API has `GET /api/v1/projects/{id}/trend` endpoint and health scores per 13-gateway architecture doc, but no user guide exists.
- **Draft Answer**: The Gateway REST API provides trend data via `GET /api/v1/projects/{id}/trend`. The UI dashboard shows violation trends over time. Health scores are computed per project.

### Gap 2: GitHub Actions Integration (Q25)

- **ID**: Q25
- **Question**: How do I integrate with GitHub Actions?
- **Impact**: GitHub Actions is the most common CI system. Without a guide, users must figure out integration themselves.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: The CLI supports `--json` output and exit codes suitable for CI. No example workflow exists.
- **Draft Answer**: Create example workflow using `pip install apme-engine@git+https://github.com/ansible/apme.git@main` and `apme check --json .`.

### Gap 3: GitLab CI Integration (Q26)

- **ID**: Q26
- **Question**: How do I integrate with GitLab CI?
- **Impact**: GitLab CI is widely used. Missing documentation forces users to experiment.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: Same CLI capabilities apply. No `.gitlab-ci.yml` example exists.

### Gap 4: Jenkins Integration (Q27)

- **ID**: Q27
- **Question**: How do I integrate with Jenkins?
- **Impact**: Many enterprises use Jenkins. Integration guide needed.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: CLI can be run in Jenkins pipelines. No example Jenkinsfile exists.

### Gap 5: Azure DevOps Integration (Q28)

- **ID**: Q28
- **Question**: How do I integrate with Azure DevOps?
- **Impact**: Azure DevOps users need guidance.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` (new file)
- **Research Notes**: No Azure Pipelines example exists.

### Gap 6: AAP/AWX Integration (Q29)

- **ID**: Q29
- **Question**: How do I use APME with AAP/AWX?
- **Impact**: AAP is the target platform for APME. Integration with execution environments and workflows is critical.
- **Suggested Location**: `docs/guides/AAP_INTEGRATION.md` (new file)
- **Research Notes**: README mentions AAP 2.5+ as the target. Roadmap mentions EE compatibility rules. No integration guide exists.
- **Draft Answer**: APME scans content for AAP 2.5+ compatibility. For EE integration, use `--ansible-core-version` flag. Future: EE compatibility rules (R505-R507) planned.

### Gap 7: Backstage Integration (Q30)

- **ID**: Q30
- **Question**: How do I use APME with Backstage?
- **Impact**: Portal/Backstage integration is relevant for platform engineering teams.
- **Suggested Location**: `docs/guides/BACKSTAGE_INTEGRATION.md` (new file)
- **Research Notes**: No Backstage plugin or integration guide exists. The Gateway API could be consumed by a Backstage plugin.

### Gap 8: Pre-commit Hooks (Q31)

- **ID**: Q31
- **Question**: How do I use APME with pre-commit hooks?
- **Impact**: Pre-commit is a popular developer workflow. Missing documentation is a usability gap.
- **Suggested Location**: `docs/guides/CI_INTEGRATION.md` or README.md
- **Research Notes**: No `.pre-commit-config.yaml` example exists. The CLI could be wrapped as a pre-commit hook.
- **Draft Answer**: Create `.pre-commit-config.yaml` entry using `apme check` as a local hook.

### Gap 9: VS Code Integration (Q34)

- **ID**: Q34
- **Question**: How do I integrate with VS Code?
- **Impact**: Editor integration is a common adoption path for local developer workflows.
- **Suggested Location**: `docs/guides/EDITOR_INTEGRATION.md` or README.md
- **Research Notes**: No VS Code extension or editor integration guide exists in the repo today.
- **Draft Answer**: Document the current status explicitly: there is no VS Code extension yet, and users should run `apme check` from the terminal or CI until an editor integration exists.

## Partial Coverage Improvements

### Partial 1: ansible-lint Comparison (Q04)

- **Current Source**: docs/rules/ANSIBLELINT_COVERAGE.md
- **Gap**: Coverage matrix exists but lacks a prose explanation of key differences and migration path.
- **Recommendation**: Add a "Why APME vs ansible-lint" section to README.md or a dedicated comparison guide.

### Partial 2: Daemon vs Pod Mode (Q10)

- **Current Source**: docs/guides/DEPLOYMENT.md
- **Gap**: Explains both modes but lacks a decision tree for when to use each.
- **Recommendation**: Add a "Which mode should I use?" section with clear guidance.

### Partial 3: Enforced Rules vs `noqa` (Q15)

- **Current Source**: `docs/guides/RULE_CONFIGURATION.md`, `graph_scanner.py`
- **Gap**: The guide documents `enforced`, but the native graph-rule scan path parses `# noqa` before violations are created. The user-facing docs should be explicit about that current limitation.
- **Recommendation**: Keep the guide aligned with implementation details until the engine supports bypassing native graph-rule `# noqa` suppressions.

### Partial 4: Custom Rules Overview (Q16)

- **Current Source**: ADR-042
- **Gap**: ADR is developer-focused, not user-facing.
- **Recommendation**: Create `docs/guides/CUSTOM_RULES.md` with high-level overview.

### Partial 5: Rule ID Conventions (Q19)

- **Current Source**: `docs/guides/RULE_CONFIGURATION.md`
- **Gap**: The guide mentions custom prefixes, but the custom-rule story is still spread across configuration docs, ADRs, and future plugin design. A dedicated custom-rules guide would be clearer for users.
- **Recommendation**: Fold rule ID conventions into `docs/guides/CUSTOM_RULES.md` alongside plugin and extension guidance.

### Partial 6: Custom OPA/Rego Rules (Q17)

- **Current Source**: docs/guides/DEVELOPMENT.md
- **Gap**: Development guide shows internal rule addition, not external/user-facing custom rules.
- **Recommendation**: Clarify distinction between internal development and plugin extensibility.

### Partial 7: Plugin Rules (Q18)

- **Current Source**: ADR-042
- **Gap**: SDK documentation planned but not yet published.
- **Recommendation**: Complete Phase 5 of ADR-042 implementation (documentation and SDK guide).

### Partial 8: Stakeholder Reports (Q22)

- **Current Source**: 13-gateway architecture doc
- **Gap**: API endpoints are documented, but there is still no guide on generating stakeholder-facing reports or choosing between dashboard summaries, trends, and proposal statistics.
- **Recommendation**: Create `docs/guides/REPORTING.md` with report examples and workflow guidance.

### Partial 9: Gateway API Metrics (Q24)

- **Current Source**: `docs/architecture/13-gateway-and-persistence.md`
- **Gap**: The architecture doc lists the available dashboard and stats endpoints, but there is no user-facing reporting guide explaining which metrics to use for dashboards, trends, or stakeholder summaries.
- **Recommendation**: Cover these endpoints in `docs/guides/REPORTING.md` with examples and usage guidance.

## Action Items

### High Priority (Core User Workflows)

- [ ] Create `docs/guides/CI_INTEGRATION.md` with examples for GitHub Actions, GitLab CI, Jenkins, Azure DevOps, and pre-commit hooks

### Medium Priority (Value Demonstration)

- [ ] Create `docs/guides/REPORTING.md` documenting Gateway API metrics, trend endpoints, AI acceptance stats, and stakeholder reporting workflows
- [ ] Add "Why APME vs ansible-lint" comparison section to README.md or a dedicated guide

### Lower Priority (Advanced/Future)

- [ ] Create `docs/guides/CUSTOM_RULES.md` with rule ID conventions and plugin SDK overview
- [ ] Create `docs/guides/AAP_INTEGRATION.md` for AAP/EE integration guidance
- [ ] Document the current "no VS Code extension yet" status and any recommended editor workflow
- [ ] Document Backstage integration pattern when plugin is available

## Next Steps

1. Review gaps with stakeholders to prioritize based on customer frequency
2. Create `CI_INTEGRATION.md` as the highest-impact missing guide
3. Create `REPORTING.md` for trends, dashboard metrics, and stakeholder workflows
4. Re-run audit after documentation updates
