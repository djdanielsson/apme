---
name: rfe-capture
description: >-
  Capture an external RFE (Jira, customer request, feature idea) using a
  research-first approach. Use when: "capture this Jira", "customer RFE",
  "feature request from X", "AAPRFE-123 should be tracked". This skill
  researches existing capabilities BEFORE creating specs to avoid duplicating
  what already exists. Do NOT use for internal feature ideas already discussed
  (use req-new instead).
argument-hint: "[Jira key or feature description]"
user-invocable: true
metadata:
  author: APME Team
  version: 1.0.0
---

# RFE Capture

Capture external RFEs with a research-first approach to avoid creating specs for capabilities that already exist.

## Why This Skill Exists

When capturing external RFEs (Jira tickets, customer requests), AI agents often create well-formatted specs without first understanding what the project already does. This leads to:
- Specs describing existing capabilities as new requirements
- Missing context about static vs. runtime boundaries
- Incorrect cross-references to related work
- Wasted review cycles

This skill enforces a **research phase before creation**.

## Arguments

If `$ARGUMENTS` is provided:
- Jira key (e.g., `AAPRFE-1607`) → fetch issue details via MCP
- Quoted description → use as feature summary
- `--quick` → abbreviated research, trust user context

## Workflow

### Phase 1: Understand the Request

**If Jira key provided:**
```
Fetching AAPRFE-1607...

Title: [title]
Description: [summary]
Labels: [labels]
Status: [status]

Is this the correct issue? (Y/N)
```

**If description provided:**
```
Feature request: "[description]"

What's the source? (Jira key, customer name, or "internal")
```

### Phase 2: Research Existing Capabilities

**CRITICAL: Do this BEFORE creating any specs.**

1. **Read CLAUDE.md** — understand project architecture, services, constraints
2. **Search for existing rules** that might address this:
   ```
   Searching validators for related functionality...
   - OPA bundle: src/apme_engine/validators/opa/bundle/
   - Native rules: src/apme_engine/validators/native/rules/
   - Ansible validator: src/apme_engine/validators/ansible/rules/
   ```
3. **Check existing specs and DRs**:
   ```
   Checking .sdlc/specs/README.md for REQ numbering...
   Checking .sdlc/decisions/README.md for related DRs...
   ```
4. **Understand ecosystem boundaries**:
   - APME = static analysis (scans content before runtime)
   - AA = runtime observability (collects data during job execution)
   - AAP = execution platform
   - Where does this request fit?

5. **Check output formats**:
   - CLI: `apme scan --json` capabilities
   - gRPC: `ScanResponse` proto structure
   - What structured data already exists?

### Phase 3: Gap Analysis

Present findings:

```
## Research Summary

### What APME Already Does
- [Rule X]: [description of existing capability]
- [Rule Y]: [description of existing capability]
- Output format: [what's available today]

### What the RFE Requests
- [capability 1]
- [capability 2]

### Actual Gap
- [specific gap, if any]
- OR: "No gap — this capability exists via [rules/output]"

### Ecosystem Consideration
- This is a [static/runtime/integration] concern
- Related existing work: [DR-NNN, REQ-NNN]
```

### Phase 4: Decision

Based on research, recommend ONE of:

| Outcome | When | Action |
|---------|------|--------|
| **No artifact needed** | Capability exists | Document in Jira comment, close |
| **Bug/task on existing REQ** | Small gap in existing feature | Create task under REQ-NNN |
| **New DR needed** | Architectural question to resolve | Use `/dr-new` |
| **New REQ needed** | Genuine new capability | Use `/req-new` |
| **Defer to other team** | Belongs in AA/AAP roadmap | Document and redirect |

```
## Recommendation

Based on research, I recommend: [outcome]

Rationale:
- [reason 1]
- [reason 2]

Proceed? (Y to execute, N to discuss, D for different approach)
```

### Phase 5: Execute (if artifact needed)

**If creating DR:**
- Use `/dr-new` with research context pre-filled
- Cross-reference related REQs and ADRs found in research

**If creating REQ:**
- Use `/req-new` with correct numbering from research
- Include "Related Artifacts" section with cross-refs
- Note existing capabilities that this builds on

**If creating task:**
- Use `/task-new` on the appropriate existing REQ
- Reference the external RFE in task description

### Phase 6: Attribution

When creating artifacts from AI-assisted research:
- "Raised By" should credit the human author
- Add note: "AI-assisted research and drafting"
- Include external reference (Jira key, customer ID)

## Examples

### Example 1: RFE for Existing Capability

```
/rfe-capture AAPRFE-1607

Fetching AAPRFE-1607...
Title: Deprecated module reports in Automation Analytics

Researching existing capabilities...
- L004 (OPA): Static deprecated modules check against curated list
- M002 (Ansible): Runtime introspection via ansible-core's module_loader
- M004 (Ansible): Removed/tombstoned module detection
- Output: ScanResponse includes violations with metadata map

Gap Analysis:
- APME already detects deprecated modules comprehensively
- CLI --json output missing metadata map (small bug)
- AA integration is separate concern (runtime vs static)

Recommendation: No new REQ needed
- Create bug task on REQ-001 for CLI metadata gap
- Note in Jira that APME already provides this capability
- AA integration tracked separately in DR-004

Proceed? (Y/N)
```

### Example 2: Genuine New Capability

```
/rfe-capture "Support scanning Terraform files for Ansible references"

Researching existing capabilities...
- No Terraform-related rules found
- Parser only handles YAML/Ansible content
- This would require new file type support

Gap Analysis:
- Genuine new capability not currently supported
- Would need parser extension + new rule category

Recommendation: New REQ needed
- REQ-012: Terraform Integration
- Phase: PHASE-004 or new phase
- Depends on: REQ-001 (parser architecture)

Proceed? (Y/N)
```

## Integration with Other Skills

| Skill | When RFE-Capture Invokes It |
|-------|----------------------------|
| `/dr-new` | When architectural question needs resolution |
| `/req-new` | When genuine new capability identified |
| `/task-new` | When small gap in existing feature |
| `/sdlc-status` | To check current REQ/DR numbering |

## Anti-Patterns to Avoid

1. **Creating specs without reading code** — always research first
2. **Duplicating existing capabilities** — check rules before spec'ing
3. **Ignoring ecosystem boundaries** — static vs runtime matters
4. **Wrong numbering** — check existing specs before assigning numbers
5. **Missing cross-references** — link to related DRs/REQs/ADRs
