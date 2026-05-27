# docs-qa-audit Procedure

When this skill is invoked, follow these steps exactly.

## Step 1: Initialize Question Set

Use these questions organized by category:

```yaml
categories:
  what_is_it:
    name: "What Is It / What Does It Do"
    questions:
      - id: Q01
        question: "What is APME and what problem does it solve?"
        keywords: ["policy", "modernization", "ansible", "aap", "validation"]
      - id: Q02
        question: "What types of Ansible content can APME scan?"
        keywords: ["playbook", "role", "collection", "inventory", "content types"]
      - id: Q03
        question: "What rules does APME enforce and why?"
        keywords: ["rule catalog", "L0", "M0", "R1", "severity"]
      - id: Q04
        question: "How does APME differ from ansible-lint?"
        keywords: ["ansible-lint", "comparison", "difference", "migrate"]
      - id: Q05
        question: "What are the severity levels and what do they mean?"
        keywords: ["severity", "critical", "error", "high", "medium", "low", "info"]

  how_to_use:
    name: "How Can I Use It"
    questions:
      - id: Q06
        question: "How do I install APME?"
        keywords: ["install", "uv", "pip", "setup", "quick start"]
      - id: Q07
        question: "How do I run a basic scan?"
        keywords: ["check", "scan", "apme check", "command"]
      - id: Q08
        question: "How do I get JSON output for automation?"
        keywords: ["--json", "json output", "machine readable", "parse"]
      - id: Q09
        question: "How do I run APME in a container?"
        keywords: ["container", "podman", "docker", "image"]
      - id: Q10
        question: "How do I use daemon vs pod mode?"
        keywords: ["daemon", "pod", "start", "local", "deployment"]

  rule_config:
    name: "Rule Configuration"
    questions:
      - id: Q11
        question: "How do I enable/disable specific rules?"
        keywords: ["enable", "disable", "rules.yml", "enabled: false"]
      - id: Q12
        question: "How do I change rule severity?"
        keywords: ["severity", "override", "severity_override"]
      - id: Q13
        question: "How do I suppress a rule for a specific line?"
        keywords: ["noqa", "suppress", "inline", "comment"]
      - id: Q14
        question: "How do I configure rules per-project?"
        keywords: [".apme", "rules.yml", "project config"]
      - id: Q15
        question: "How do I enforce rules and ignore noqa comments?"
        keywords: ["enforced", "ignore noqa", "strict"]

  custom_rules:
    name: "Bring Your Own Rules"
    questions:
      - id: Q16
        question: "Can I add custom rules?"
        keywords: ["custom", "byo", "bring your own", "extend"]
      - id: Q17
        question: "How do I write a custom OPA/Rego rule?"
        keywords: ["opa", "rego", "custom bundle", "policy"]
      - id: Q18
        question: "How do I add custom rules via plugins?"
        keywords: ["plugin", "EXT-", "grpc", "third-party"]
      - id: Q19
        question: "What rule ID conventions should custom rules follow?"
        keywords: ["rule id", "convention", "L0", "M0", "prefix"]

  demonstrating_value:
    name: "Demonstrating Value"
    questions:
      - id: Q20
        question: "How do I show before/after remediation?"
        keywords: ["diff", "before", "after", "remediate", "fix"]
      - id: Q21
        question: "How do I track improvement over time?"
        keywords: ["health score", "trend", "progress", "improvement"]
      - id: Q22
        question: "How do I generate reports for stakeholders?"
        keywords: ["report", "stakeholder", "summary", "gateway"]
      - id: Q23
        question: "How do I measure AI fix acceptance rates?"
        keywords: ["ai", "acceptance", "confidence", "approval"]
      - id: Q24
        question: "What metrics does the Gateway API provide?"
        keywords: ["metrics", "api", "gateway", "statistics"]

  integrations:
    name: "Integration with Existing Tools"
    questions:
      - id: Q25
        question: "How do I integrate with GitHub Actions?"
        keywords: ["github", "actions", "workflow", "ci"]
      - id: Q26
        question: "How do I integrate with GitLab CI?"
        keywords: ["gitlab", "ci", "pipeline"]
      - id: Q27
        question: "How do I integrate with Jenkins?"
        keywords: ["jenkins", "pipeline", "groovy"]
      - id: Q28
        question: "How do I integrate with Azure DevOps?"
        keywords: ["azure", "devops", "pipeline"]
      - id: Q29
        question: "How do I use APME with AAP/AWX?"
        keywords: ["aap", "awx", "controller", "tower"]
      - id: Q30
        question: "How do I use APME with Backstage?"
        keywords: ["backstage", "portal", "plugin"]
      - id: Q31
        question: "How do I use APME with pre-commit hooks?"
        keywords: ["pre-commit", "hook", "git"]
      - id: Q32
        question: "How do I migrate from ansible-lint?"
        keywords: ["migrate", "ansible-lint", "transition"]
      - id: Q33
        question: "How do I use APME in an air-gapped environment?"
        keywords: ["air-gap", "offline", "disconnected"]
      - id: Q34
        question: "How do I integrate with VS Code?"
        keywords: ["vscode", "vs code", "editor", "extension"]
```

## Step 2: Search Documentation

For each question, search these locations in order:

1. **Primary user docs** (highest weight):
   ```
   docs/guides/*.md
   README.md
   docs/rules/RULE_CATALOG.md
   ```

2. **Secondary docs** (partial coverage):
   ```
   .sdlc/adrs/*.md
   .sdlc/specs/*.md
   docs/reports/*.md (exclude docs-qa-audit-*.md to avoid self-matching)
   ```

3. **Code as documentation** (lowest weight):
   ```
   src/apme_engine/cli/*.py (--help text)
   src/apme_engine/cli/_rules_yml.py
   src/apme_gateway/api/router.py
   ```

Use `grep -l` with keywords to find matching files, then read relevant sections.

## Step 3: Score Each Question

For each question, determine status:

| Status | Criteria |
|--------|----------|
| ✓ Covered | Clear, user-facing answer in `docs/guides/` or `README.md` |
| ⚠ Partial | Answer exists but: only in ADRs, incomplete, or buried in code |
| ✗ Gap | No answer found, or only implementation exists |

Record:
- `status`: ✓, ⚠, or ✗
- `source`: File path and section/line
- `excerpt`: Brief quote showing the answer (if found)
- `notes`: Why partial, or what's missing

## Step 4: Generate Coverage Matrix

Create markdown table. **Important:** Since reports live in `docs/reports/`, use `../../` prefix for repo-root links.

```markdown
## Coverage Matrix

| ID | Category | Question | Status | Source |
|----|----------|----------|--------|--------|
| Q01 | What Is It | What is APME and what problem does it solve? | ✓ | [README.md#overview](../../README.md#overview) |
```

## Step 5: Handle Gaps

For each gap (✗) or significant partial (⚠):

### 5a. Check for Existing DR
```bash
grep -l "<question keywords>" .sdlc/decisions/open/*.md
```

### 5b. If No DR Exists, Create One
Use `/dr-new` skill with:
- Title: Documentation gap — <question summary>
- Context: User question that cannot be answered
- Options: Which doc to add it to

### 5c. Draft Answer Stub
Research the answer from:
- ADRs (architectural context)
- Code (actual behavior)
- Existing partial docs

Create draft in `docs/drafts/` or suggest PR content.

## Step 6: Generate Report

Write the report to `docs/reports/docs-qa-audit-YYYY-MM-DD.md` by default. If
the user invoked the skill with `--output path/to/report.md`, write the report
to that explicit path instead:

```markdown
# Documentation Q&A Audit — YYYY-MM-DD

## Executive Summary

- **Total Questions**: X
- **Covered**: Y (Z%)
- **Partial**: A (B%)
- **Gaps**: C (D%)

## Coverage by Category

| Category | Covered | Partial | Gap |
|----------|---------|---------|-----|
| What Is It | 4/5 | 1/5 | 0/5 |
| ... | ... | ... | ... |

## Coverage Matrix

[Full table from Step 4]

## Gap Analysis

### Gap 1: <Question>
- **ID**: Q##
- **Question**: Full question text
- **Impact**: Why this matters to users
- **Suggested Location**: `docs/guides/FOO.md`
- **Research Notes**: What we found in code/ADRs
- **DR**: [DR-0XX](../../.sdlc/decisions/open/DR-0XX.md) (if created)

## Partial Coverage Improvements

### Partial 1: <Question>
- **Current Source**: ADR-0XX
- **Gap**: Not user-facing / incomplete
- **Recommendation**: Add section to `docs/guides/FOO.md`

## Action Items

- [ ] DR-0XX: <gap summary>
- [ ] Update `docs/guides/FOO.md` with <topic>
- [ ] Create `docs/guides/BAR.md` for <new guide>

## Next Steps

1. Review gaps with stakeholders
2. Prioritize based on customer frequency
3. Create PRs for draft answers
4. Re-run audit after updates
```

## Step 7: Summarize to User

After generating the report, output:
1. Coverage percentage summary
2. List of gaps found
3. DRs created (if any)
4. Path to full report
