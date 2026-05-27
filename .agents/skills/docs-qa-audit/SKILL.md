---
name: docs-qa-audit
description: >
  Audit documentation coverage against common user questions. Generates a Q&A
  matrix, searches docs/code for answers, flags gaps, and creates DRs for
  missing content. Use when asked to "audit docs", "check documentation
  coverage", "what questions can users answer", or before releases/demos.
argument-hint: "[--output path/to/report.md]"
user-invocable: true
metadata:
  author: APME Team
  version: 1.0.0
---

# docs-qa-audit

Audit documentation coverage against common user questions. Generates a Q&A matrix, searches docs/code for answers, flags gaps, and creates DRs for missing content.

## Trigger

Use when:
- "audit docs", "check documentation coverage", "docs qa"
- "what questions can users answer", "documentation gaps"
- "validate user guides", "check we have answers"
- Preparing for customer demos or releases

## Output

Markdown report written by default to `docs/reports/docs-qa-audit-YYYY-MM-DD.md`.
If invoked with `--output path/to/report.md`, write the report to that path
instead. The report contains:
1. **Coverage Matrix** — Questions with status (✓ covered / ⚠ partial / ✗ gap)
2. **Source References** — Links to docs/code that answer each question
3. **Gap Analysis** — Missing answers with suggested doc locations
4. **Action Items** — DRs created for gaps, draft answer stubs for documentation

## Question Categories

### 1. What Is It / What Does It Do
- What is APME and what problem does it solve?
- What types of Ansible content can APME scan?
- What rules does APME enforce and why?
- How does APME differ from ansible-lint?
- What are the severity levels and what do they mean?

### 2. How Can I Use It
- How do I install APME?
- How do I run a basic scan?
- How do I get JSON output for automation?
- How do I run APME in a container?
- How do I use the daemon vs pod mode?

### 3. Rule Configuration
- How do I enable/disable specific rules?
- How do I change rule severity?
- How do I suppress a rule for a specific line (noqa)?
- How do I configure rules per-project?
- How do I enforce rules and ignore noqa comments?

### 4. Bring Your Own Rules
- Can I add custom rules?
- How do I write a custom OPA/Rego rule?
- How do I add custom rules via plugins?
- What rule ID conventions should custom rules follow?

### 5. Demonstrating Value
- How do I show before/after remediation?
- How do I track improvement over time (health score)?
- How do I generate reports for stakeholders?
- How do I measure AI fix acceptance rates?
- What metrics does the Gateway API provide?

### 6. Integration with Existing Tools
- How do I integrate with GitHub Actions?
- How do I integrate with GitLab CI?
- How do I integrate with Jenkins?
- How do I integrate with Azure DevOps?
- How do I use APME with AAP/AWX?
- How do I use APME with Backstage?
- How do I use APME with pre-commit hooks?
- How do I migrate from ansible-lint?
- How do I use APME in an air-gapped environment?
- How do I integrate with VS Code?

## Procedure

See [procedure.md](procedure.md) for the detailed step-by-step implementation guide.

### Overview

1. **Load Question Set** — Use the categories above
2. **Search Documentation** — Glob `docs/**/*.md`, `README.md`, `.sdlc/**/*.md`
3. **Search Code** — Grep for CLI help, config loaders, API endpoints
4. **Score Coverage**:
   - ✓ **Covered**: Clear answer in user-facing docs
   - ⚠ **Partial**: Answer exists but incomplete or only in code/ADRs
   - ✗ **Gap**: No answer found
5. **Generate Matrix** — Markdown table with question, status, source
6. **Handle Gaps**:
   - Create DR for each gap (if not already exists)
   - Draft answer stub based on code/ADR research
   - Suggest target doc file for the answer
7. **Output Report** — Write to `docs/reports/docs-qa-audit-YYYY-MM-DD.md`

## Search Locations

| Content Type | Locations |
|--------------|-----------|
| User guides | `docs/guides/*.md` |
| README | `README.md` |
| Rule docs | `docs/rules/*.md`, `src/**/rules/*.md` |
| API docs | `docs/architecture/*.md`, `docs/design/*.md`, `src/apme_gateway/api/` |
| ADRs | `.sdlc/adrs/*.md` |
| CLI help | `src/apme_engine/cli/*.py` |
| Config | `src/apme_engine/cli/_rules_yml.py`, `.apme/` patterns |

## Example Output

```markdown
# Documentation Q&A Audit — 2026-05-21

## Coverage Summary
- **Covered**: 18/25 (72%)
- **Partial**: 4/25 (16%)
- **Gaps**: 3/25 (12%)

## Coverage Matrix

| # | Question | Status | Source |
|---|----------|--------|--------|
| 1 | What is APME? | ✓ | [README.md#overview](../../README.md#overview) |
| 2 | How do I install? | ✓ | [README.md#quick-start](../../README.md#quick-start) |
| 3 | How do I write custom OPA rules? | ⚠ | ADR-042 (not user-facing) |
| 4 | How do I use with Backstage? | ✗ | — |

## Gaps & Actions

### Gap: Backstage Integration
- **Question**: How do I use APME with Backstage?
- **DR Created**: DR-018-backstage-integration-guide
- **Suggested Location**: `docs/guides/BACKSTAGE_INTEGRATION.md`
- **Draft Answer**: [See PR #XXX]
```

## Notes

- Run periodically before releases or customer engagements
- Output is designed to feed presentation decks or release-readiness reviews
- Gaps with DRs can be tracked via `/sdlc-status`
- **Link format**: When the report lives in `docs/reports/`, use `../../` prefix for repo-root links
