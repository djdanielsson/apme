# Documentation Q&A Audit - 2026-06-10

## Executive Summary

- **Total Questions**: 34
- **Covered** (✓): 16 (47%)
- **Partial** (⚠): 13 (38%)
- **Gaps** (✗): 5 (15%)

Progress since the [2026-05-21 audit](docs-qa-audit-2026-05-21.md). CI/CD integration has a GitHub Actions example in CLI.md and examples/ci/; GitLab CI and Jenkins are mentioned in the capabilities table but have no standalone examples, and Azure DevOps is not documented at all. Remaining gaps are AAP/AWX integration, Backstage (in progress via PR #298), VS Code extension, and reporting/metrics guides.

## Coverage by Category

| Category | Covered | Partial | Gap | Score |
|----------|---------|---------|-----|-------|
| What Is It / What Does It Do | 4/5 | 1/5 | 0/5 | 90% |
| How Can I Use It | 5/5 | 0/5 | 0/5 | 100% |
| Rule Configuration | 4/5 | 1/5 | 0/5 | 90% |
| Bring Your Own Rules | 0/4 | 4/4 | 0/4 | 50% |
| Demonstrating Value | 1/5 | 3/5 | 1/5 | 50% |
| Integration with Existing Tools | 2/10 | 4/10 | 4/10 | 40% |

## Coverage Matrix

| ID | Category | Question | Status | Source |
|----|----------|----------|--------|--------|
| Q01 | What Is It / What Does It Do | What is APME and what problem does it solve? | ✓ | [README.md#what-apme-is](../../README.md#what-apme-is), [README.md#key-features](../../README.md#key-features) |
| Q02 | What Is It / What Does It Do | What types of Ansible content can APME scan? | ✓ | [README.md#what-apme-is](../../README.md#what-apme-is), [README.md#architecture-at-a-glance](../../README.md#architecture-at-a-glance) |
| Q03 | What Is It / What Does It Do | What rules does APME enforce and why? | ✓ | [RULE_CATALOG.md](../rules/RULE_CATALOG.md) |
| Q04 | What Is It / What Does It Do | How does APME differ from ansible-lint? | ⚠ | [ANSIBLELINT_COVERAGE.md](../rules/ANSIBLELINT_COVERAGE.md) |
| Q05 | What Is It / What Does It Do | What are the severity levels and what do they mean? | ✓ | [RULE_CATALOG.md](../rules/RULE_CATALOG.md) |
| Q06 | How Can I Use It | How do I install APME? | ✓ | [README.md#getting-started](../../README.md#getting-started) |
| Q07 | How Can I Use It | How do I run a basic scan? | ✓ | [README.md#try-it-now](../../README.md#try-it-now), [CLI.md](../guides/CLI.md) |
| Q08 | How Can I Use It | How do I get JSON output for automation? | ✓ | [README.md#try-it-now](../../README.md#try-it-now), [CLI.md](../guides/CLI.md) |
| Q09 | How Can I Use It | How do I run APME in a container? | ✓ | [README.md](../../README.md), [DEPLOYMENT.md](../guides/DEPLOYMENT.md) |
| Q10 | How Can I Use It | How do I use daemon vs pod mode? | ✓ | [DEPLOYMENT.md](../guides/DEPLOYMENT.md), [CLI.md](../guides/CLI.md) |
| Q11 | Rule Configuration | How do I enable/disable specific rules? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q12 | Rule Configuration | How do I change rule severity? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q13 | Rule Configuration | How do I suppress a rule for a specific line? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q14 | Rule Configuration | How do I configure rules per-project? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q15 | Rule Configuration | How do I enforce rules and ignore noqa comments? | ⚠ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q16 | Bring Your Own Rules | Can I add custom rules? | ⚠ | [ADR-042](../../.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q17 | Bring Your Own Rules | How do I write a custom OPA/Rego rule? | ⚠ | [DEVELOPMENT.md](../guides/DEVELOPMENT.md) |
| Q18 | Bring Your Own Rules | How do I add custom rules via plugins? | ⚠ | [ADR-042](../../.sdlc/adrs/ADR-042-third-party-plugin-services.md) |
| Q19 | Bring Your Own Rules | What rule ID conventions should custom rules follow? | ⚠ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) |
| Q20 | Demonstrating Value | How do I show before/after remediation? | ⚠ | [README.md#remediation](../../README.md#remediation) (basic example only, no detailed guide) |
| Q21 | Demonstrating Value | How do I track improvement over time? | ✗ | No reporting guide yet |
| Q22 | Demonstrating Value | How do I generate reports for stakeholders? | ⚠ | [13-gateway-and-persistence.md](../architecture/13-gateway-and-persistence.md) (architecture doc, not user guide) |
| Q23 | Demonstrating Value | How do I measure AI fix acceptance rates? | ✓ | [RULE_CONFIGURATION.md](../guides/RULE_CONFIGURATION.md) (documents `GET /api/v1/stats/ai-acceptance` endpoint) |
| Q24 | Demonstrating Value | What metrics does the Gateway API provide? | ⚠ | [13-gateway-and-persistence.md](../architecture/13-gateway-and-persistence.md) (architecture doc, not user guide) |
| Q25 | Integration with Existing Tools | How do I integrate with GitHub Actions? | ✓ | [CLI.md](../guides/CLI.md), [examples/ci/github-actions/](../../examples/ci/github-actions/) |
| Q26 | Integration with Existing Tools | How do I integrate with GitLab CI? | ⚠ | [CLI.md](../guides/CLI.md) (mentioned in capabilities table only, no example) |
| Q27 | Integration with Existing Tools | How do I integrate with Jenkins? | ⚠ | [CLI.md](../guides/CLI.md) (mentioned in capabilities table only, no example) |
| Q28 | Integration with Existing Tools | How do I integrate with Azure DevOps? | ✗ | Not documented (CLI.md does not mention Azure DevOps) |
| Q29 | Integration with Existing Tools | How do I use APME with AAP/AWX? | ✗ | No AAP_INTEGRATION.md yet |
| Q30 | Integration with Existing Tools | How do I use APME with Backstage? | ✗ | PR #298 in progress (draft) |
| Q31 | Integration with Existing Tools | How do I integrate with pre-commit hooks? | ✓ | [CLI.md](../guides/CLI.md), [examples/ci/pre-commit/](../../examples/ci/pre-commit/) |
| Q32 | Integration with Existing Tools | How do I migrate from ansible-lint? | ⚠ | [ANSIBLELINT_COVERAGE.md](../rules/ANSIBLELINT_COVERAGE.md) (rule coverage matrix, not a migration guide with prose narrative or step-by-step workflow) |
| Q33 | Integration with Existing Tools | How do I use APME in an air-gapped environment? | ⚠ | [DEPLOYMENT.md#custom-ca-certificates](../guides/DEPLOYMENT.md#custom-ca-certificates) (covers custom CA trust, not full air-gapped deployment guidance) |
| Q34 | Integration with Existing Tools | How do I integrate with VS Code? | ✗ | No VS Code extension exists yet |

## Changes Since 2026-05-21 Audit

### Gaps Closed

| ID | Question | Resolution |
|----|----------|------------|
| Q10 | Daemon vs pod mode | CLI.md now has clear comparison table and decision guidance |
| Q25 | GitHub Actions | CLI.md has inline example + examples/ci/github-actions/ has full workflows |
| Q31 | Pre-commit | CLI.md has config example + examples/ci/pre-commit/ has full setup |

### New Documentation Added

| Document | Purpose |
|----------|---------|
| [examples/ci/](../../examples/ci/) | Copy-paste CI/CD workflow examples |
| [examples/ci/github-actions/](../../examples/ci/github-actions/) | GitHub Actions workflows (check, format, hosted) |
| [examples/ci/pre-commit/](../../examples/ci/pre-commit/) | Pre-commit hook configuration |

### PRs In Progress

| PR | Title | Status | Closes |
|----|-------|--------|--------|
| #304 | CI/CD integration guide | In review (feedback being addressed) | Consolidates CI guidance |
| #298 | Backstage plugin integration | Draft | Q30 |
| #338 | M031 Sensitive tag rule | In review (feedback being addressed) | New rule |

## Remaining Gaps

### Gap 1: Tracking Improvement Over Time (Q21)

- **Impact**: Stakeholders want to see progress over time. Without guidance, users cannot demonstrate ROI.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Notes**: Gateway API has trend endpoints per architecture doc, but no user-facing guide for historical tracking exists.

### Gap 2: AAP/AWX Integration (Q29)

- **Impact**: AAP is the target platform for APME. Integration guidance is critical for enterprise adoption.
- **Suggested Location**: `docs/guides/AAP_INTEGRATION.md` (new file)
- **Notes**: APME targets AAP 2.5+ environments (per CLAUDE.md project overview). EE rules planned (R505-R507).

### Gap 3: Backstage Integration (Q30)

- **Impact**: Portal/Backstage integration relevant for platform engineering teams.
- **Status**: PR #298 (draft) adds Backstage plugin integration support (see ADR-030 for frontend deployment model, ADR-029 for Gateway API context).
- **Notes**: Will be resolved when PR merges.

### Gap 4: VS Code Integration (Q34)

- **Impact**: Editor integration is a common adoption path for developer workflows.
- **Status**: No VS Code extension exists. Could document workaround (terminal usage).
- **Notes**: Consider explicit "no extension yet" statement in docs.

### Gap 5: User-Facing Reporting Guide (supplements Q22/Q24)

- **Impact**: Q22/Q24 are partial (architecture doc covers the API) but lack a user-facing guide for generating reports and interpreting Gateway metrics.
- **Suggested Location**: `docs/guides/REPORTING.md` (new file)
- **Notes**: Would promote Q22/Q24 from partial to covered.

### Gap 6: Azure DevOps Integration (Q28)

- **Impact**: Azure DevOps users have no integration guidance.
- **Status**: Not mentioned in CLI.md. PR #304 (CI/CD guide) includes Azure DevOps examples.
- **Notes**: Will be resolved when PR #304 merges.

## Partial Coverage Improvements Needed

### Partial 1: ansible-lint Comparison (Q04)

- **Current**: ANSIBLELINT_COVERAGE.md has rule mapping
- **Gap**: Lacks prose explanation of key differences and migration narrative
- **Recommendation**: Add "Why APME vs ansible-lint" section

### Partial 2: Custom Rules (Q16-Q19)

- **Current**: ADR-042 and DEVELOPMENT.md have technical details
- **Gap**: No user-facing custom rules guide
- **Recommendation**: Create `docs/guides/CUSTOM_RULES.md` when plugin SDK ships

## Action Items

### High Priority

- [ ] Merge PR #304 (CI/CD integration guide) - in review, feedback being addressed
- [ ] Merge PR #338 (M031 rule) - in review, feedback being addressed

### Medium Priority

- [ ] Create `docs/guides/REPORTING.md` for Gateway metrics, trends, and stakeholder workflows
- [ ] Create `docs/guides/AAP_INTEGRATION.md` for AAP/EE integration guidance
- [ ] Create `docs/guides/AIR_GAPPED.md` for fully air-gapped deployment guidance
- [ ] Review and advance PR #298 (Backstage integration)

### Lower Priority

- [ ] Create `docs/guides/CUSTOM_RULES.md` when plugin SDK is complete
- [ ] Document VS Code workaround (terminal usage) or "no extension yet" status
- [ ] Add "Why APME vs ansible-lint" comparison section

## Score Comparison

Scores use weighted formula: (covered + partial × 0.5) / total × 100.

| Category | May 21 | Jun 10 | Change |
|----------|--------|--------|--------|
| What Is It / What Does It Do | 90% | 90% | — |
| How Can I Use It | 90% | 100% | +10% |
| Rule Configuration | 90% | 90% | — |
| Bring Your Own Rules | 50% | 50% | — |
| Demonstrating Value | 60% | 50% | -10% |
| Integration with Existing Tools | 20% | 40% | +20% |
| **Overall (weighted)** | **60%** | **66%** | **+6%** |
