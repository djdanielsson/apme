# APME Agent Configurations

This document defines the specialized agents used in APME development.

## Agent Roles

### 1. Spec Writer Agent

**Purpose**: Creates and maintains specification documents.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/templates/requirement.md`
- `.sdlc/templates/task.md`
- `.sdlc/context/project-overview.md`

**Capabilities**:
- Write requirement specifications
- Create task breakdowns
- Draft architecture decision records
- Ensure spec completeness

**Constraints**:
- Must use templates from `.sdlc/templates/`
- Must link related specs (REQ -> TASK)
- Must include acceptance criteria

---

### 2. Scanner Implementation Agent

**Purpose**: Implements the ARI wrapper and scanning functionality.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-001-scanner/`
- `.sdlc/context/dependencies.md`

**Capabilities**:
- Integrate with ARI library
- Parse ARI output formats
- Categorize detected issues
- Generate scan reports

**Constraints**:
- Must preserve ARI's original functionality
- Must handle all ARI output formats
- Must not modify playbook files during scanning

---

### 3. Rewriter Implementation Agent

**Purpose**: Implements the LangGraph-based rewriting workflow.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-002-rewriter/`
- `.sdlc/context/architecture.md`

**Capabilities**:
- Build LangGraph state machines
- Implement YAML transformations
- Apply FQCN fixes
- Handle deprecated module replacements

**Constraints**:
- Must preserve YAML comments
- Must maintain playbook semantics
- Must create backups before modifications
- Must be idempotent

---

### 4. Dashboard Implementation Agent

**Purpose**: Implements the Streamlit dashboard.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-003-dashboard/`

**Capabilities**:
- Create Streamlit interfaces
- Visualize scan results
- Display modernization progress
- Generate reports

**Constraints**:
- Must handle large datasets efficiently
- Must be responsive
- Must support export functionality

---

### 5. Integration Agent

**Purpose**: Creates CI/CD integrations and examples.

**Context Files**:
- `CLAUDE.md`
- `.sdlc/specs/REQ-004-integration/`
- `examples/`

**Capabilities**:
- Create GitHub Actions workflows
- Create AAP pre-flight checks
- Write integration documentation
- Create example configurations

**Constraints**:
- Must be copy-paste ready
- Must include clear documentation
- Must handle common edge cases

---

## Agent Workflow

```
┌─────────────────┐
│  Spec Writer    │ ──► Creates REQ and TASK specs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Implementation │ ──► Scanner, Rewriter, Dashboard agents
│     Agents      │     implement based on specs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Integration    │ ──► Creates CI/CD examples and docs
│     Agent       │
└─────────────────┘
```

## Handoff Protocol

When transitioning between agents:

1. **Completing Agent**:
   - Update task status to `Complete`
   - Document any deviations from spec
   - Note open questions for next agent

2. **Receiving Agent**:
   - Read CLAUDE.md for context
   - Read relevant REQ and TASK specs
   - Check for notes from previous agent
   - Continue from documented state

## Project Skills

This project defines agent skills in `.agents/skills/`. When the user types a
`/slash-command`, check `.agents/skills/<command-name>/SKILL.md` **before doing
anything else**. If a matching skill exists, read it and follow its instructions.

| Command | Purpose |
|---------|---------|
| `/adr-new` | Create architectural decision record |
| `/dr-new` | Capture blocking question |
| `/dr-review` | Review decision records |
| `/lean-ci` | CI workflow helpers |
| `/phase-new` | Create project phase |
| `/pr-review` | Handle PR review feedback |
| `/prd-import` | Import product requirements |
| `/req-new` | Create requirement spec |
| `/review-contributor-pr` | Review external contributor PRs |
| `/sdlc-status` | SDLC dashboard status |
| `/submit-pr` | Create and submit pull requests |
| `/task-new` | Create implementation task |
| `/workflow` | Development workflow guidance |

## Design Thinking

### Sunk cost fallacy

Do not defend existing code simply because effort was invested in it. If a
fix requires increasingly complex workarounds — offset detection, heuristic
correction, retry loops — the underlying abstraction is likely wrong.
Discard the existing approach and redesign the interface.

**Two workarounds for the same interface = redesign the interface.**

### Design LLM contracts around LLM strengths

Never ask an LLM to be precise about line numbers, character offsets, or
positional arithmetic. LLMs are good at understanding and transforming
text. Design contracts where the LLM returns **content** and we handle
**positioning** and reassembly.

### Treat directional feedback as architectural

When a human says "we're too coupled to X" or "why do we need Y," treat
it as an architectural concern, not a narrow bug. Step back to first
principles before writing code. Ask: *"What would this look like if we
didn't have X at all?"*

### Two failed attempts = wrong abstraction

If the same class of failure recurs after two fix attempts, do not attempt
a third fix at the same level. Escalate to a design review of the
interface itself. The pattern of repeated failure is the evidence.

## Quality Assurance

All agents must:

1. Follow the spec exactly
2. Run verification steps
3. Update task status
4. Commit with proper message format
5. Flag any spec ambiguities
