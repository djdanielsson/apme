# Remediation Engine Design

## Overview

The remediation engine is a separate service that consumes scan violations and produces file patches. It is **not** the formatter. The formatter is a blind pre-pass that normalizes YAML style; the remediation engine is a violation-driven transform pipeline that fixes detected issues.

```
┌──────────┐     ┌─────────────┐     ┌──────────┐     ┌──────────────────┐     ┌──────────┐
│ Formatter│ ──► │ Idempotency │ ──► │  Scan    │ ──► │  Remediation    │ ──► │ Re-scan  │
│ (Phase 1)│     │    Gate     │     │ (engine  │     │    Engine       │     │          │
│          │     │             │     │  + all   │     │                 │     │          │
│ blind    │     │ format again│     │ validtrs)│     │ partition →     │     │ verify   │
│ pre-pass │     │ assert zero │     │          │     │ transform / AI  │     │ fixes    │
│          │     │ diffs       │     │          │     │                 │     │          │
└──────────┘     └─────────────┘     └──────────┘     └──────────────────┘     └──────────┘
                                                              │                      │
                                                              │    ┌─────────────────┘
                                                              │    │ count decreased?
                                                              │    │ repeat (max N)
                                                              ▼    ▼
                                                        ┌──────────────┐
                                                        │   Report     │
                                                        │  (converged  │
                                                        │   or bail)   │
                                                        └──────────────┘
```

## Why the Formatter Is Not Part of the Remediation Engine

| | Formatter (Phase 1) | Remediation Engine (Phase 2+) |
|---|---|---|
| **Input** | Raw YAML text | Violations from a scan |
| **Trigger** | Always runs (blind pre-pass) | Only runs when violations exist |
| **Logic** | Fixed transforms: tabs, indentation, key order, Jinja spacing | Rule-specific transforms + AI escalation |
| **Needs a scan?** | No | Yes |
| **Goal** | Canonical formatting so downstream diffs are clean | Fix detected issues |

Routing the formatter through the remediation engine would require:
1. Running a scan before formatting (to produce violations for the engine to consume)
2. Inventing artificial "formatting violation" rules that don't exist today
3. Creating a circular dependency: format needs scan, scan assumes formatted input

The formatter is a **pre-condition** for the remediation engine. `apme-scan format` works without any scan infrastructure — fast, standalone, no containers needed.

## Fix Pipeline

The `apme-scan fix` command orchestrates the full pipeline:

```
Phase 1: Format
  └─► format all YAML files (tabs, indentation, key order, Jinja spacing)
  └─► write changes if --apply

Phase 2: Idempotency Gate
  └─► format again
  └─► assert zero diffs (if not: formatter bug, abort)

Phase 3: Scan
  └─► run engine (parse → annotate → hierarchy)
  └─► fan out to all validators (Native, OPA, Ansible, Gitleaks)
  └─► merge + deduplicate violations

Phase 4: Remediate
  └─► partition violations via is_finding_resolvable()
  └─► apply deterministic transforms (Transform Registry)
  └─► escalate non-fixable to AI (OpenLLM via gRPC) if available
  └─► apply accepted patches

Phase 5: Re-scan + Convergence
  └─► re-scan to verify fixes
  └─► if violation count decreased → repeat from Phase 4 (max --max-passes)
  └─► if count stable or increased → bail (oscillation)

Phase 6: Report
  └─► summary: fixed, remaining (manual), AI-proposed, failed
```

### Where Each Component Lives

| Component | Location | Why |
|-----------|----------|-----|
| Formatter | CLI (in-process) or Primary (`Format` RPC) | No scan needed; operates on raw files |
| Scan | Primary service (gRPC) or CLI (in-process) | Already implemented |
| Remediation Engine | Primary service (`Fix` RPC) | Needs access to scan results and file content; can call OpenLLM |
| Transform Registry | `src/apme_engine/remediation/transforms/` | Pure functions, no container needed |
| AI Escalation | OpenLLM daemon (gRPC) | Separate container, optional |

## Finding Partition

### `is_finding_resolvable()`

The partition function is the sole decision point between deterministic and AI/manual paths:

```python
def is_finding_resolvable(violation: dict, registry: TransformRegistry) -> bool:
    """Return True if the violation has a registered deterministic transform."""
    return violation.get("rule_id", "") in registry
```

This is intentionally simple. A violation is resolvable if and only if the transform registry has a function for that rule ID. No heuristics, no guessing.

### Rule Metadata

Each rule across all validators declares a `fixable` attribute in its metadata. This is informational — it tells the user "this rule has an automatic fix available" — but the actual decision is made by the registry lookup.

```python
@dataclass
class RuleMetadata:
    rule_id: str
    level: str          # "error", "warning", "info"
    fixable: bool       # True if a transform exists
    description: str
```

The `fixable` flag is set to `True` when a corresponding transform is registered. Rules without transforms have `fixable = False` and are candidates for AI escalation or manual review.

## Transform Registry

### Design

```python
from typing import Callable, NamedTuple

class TransformResult(NamedTuple):
    content: str        # modified file content
    applied: bool       # True if a change was made

TransformFn = Callable[[str, dict], TransformResult]
# TransformFn(file_content: str, violation: dict) -> TransformResult


class TransformRegistry:
    """Maps rule IDs to deterministic fix functions."""

    def __init__(self):
        self._transforms: dict[str, TransformFn] = {}

    def register(self, rule_id: str, fn: TransformFn) -> None:
        self._transforms[rule_id] = fn

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self._transforms

    def apply(self, rule_id: str, content: str, violation: dict) -> TransformResult:
        fn = self._transforms.get(rule_id)
        if fn is None:
            return TransformResult(content=content, applied=False)
        return fn(content, violation)
```

### Transform Implementation Rules

1. **Operate on YAML AST** — use `FormattedYAML` (ruamel round-trip) to preserve comments and formatting
2. **Single responsibility** — one transform per rule ID; a transform fixes exactly the issue its rule detects
3. **Idempotent** — applying a transform to already-fixed content produces no change
4. **Independently testable** — each transform has its own unit test with before/after YAML strings
5. **No side effects** — transforms receive content + violation, return content; they do not write files

### Example Transform

```python
def fix_missing_mode(content: str, violation: dict) -> TransformResult:
    """L021: add mode: '0644' to file/copy/template tasks missing explicit mode."""
    yaml = FormattedYAML(typ="rt", pure=True, version=(1, 1))
    data = yaml.load(content)

    # Navigate to the task identified by the violation
    task = _find_task_at_line(data, violation.get("line", 0))
    if task is None:
        return TransformResult(content=content, applied=False)

    module_key = _get_module_key(task)
    if module_key and "mode" not in task[module_key]:
        task[module_key]["mode"] = "0644"
        return TransformResult(content=yaml.dumps(data), applied=True)

    return TransformResult(content=content, applied=False)
```

### File Organization

```
src/apme_engine/remediation/
  ├── __init__.py
  ├── engine.py              # RemediationEngine class (convergence loop)
  ├── partition.py            # is_finding_resolvable()
  ├── registry.py             # TransformRegistry
  ├── ai_escalation.py        # OpenLLM gRPC client
  └── transforms/
      ├── __init__.py          # auto-registers all transforms
      ├── L021_missing_mode.py
      ├── L007_shell_to_command.py
      ├── M001_fqcn.py
      └── ...
```

## AI Escalation Path

When `is_finding_resolvable()` returns `False` and an OpenLLM service is available, the remediation engine escalates to AI.

### Request Packaging

Each violation is packaged with context for the LLM:

```python
@dataclass
class AIRemediationRequest:
    rule_id: str
    level: str
    message: str
    file_path: str
    line: int
    code_window: str        # 10 lines before + after the violation
    file_content: str       # full file (for broader context)
    ansible_version: str    # target version (e.g., "2.20")
```

### Structured Prompt

```
You are an Ansible modernization assistant. A static analysis rule has
flagged an issue in the following YAML file.

Rule: {rule_id}
Message: {message}
File: {file_path}
Line: {line}

Code context (lines {start}-{end}):
```yaml
{code_window}
```

Provide a fix for this issue. Respond with ONLY valid YAML for the
corrected section. Preserve comments and formatting. If you cannot
fix it with confidence, respond with "SKIP".
```

### Response Schema

```python
@dataclass
class AIRemediationResponse:
    suggested_code: str     # corrected YAML (or "SKIP")
    confidence: float       # 0.0-1.0
    reasoning: str          # why this fix is correct
    applicable: bool        # False if LLM says "SKIP"
```

### CLI Modes

| Flag | Behavior |
|------|----------|
| `--no-ai` | Skip AI entirely; report non-fixable violations as "manual review" |
| `--auto` | Apply AI patches without prompting (CI mode) |
| (default) | Show AI-proposed patch + diff, prompt user to accept/reject |
| `--min-confidence 0.8` | Only apply AI patches with confidence >= threshold |

### Graceful Degradation

If `OPENLLM_GRPC_ADDRESS` is unset or the service is unreachable, the remediation engine skips AI escalation silently. Non-fixable violations are reported as "manual review required." The `fix` pipeline never fails due to missing AI.

## Convergence Loop

### Algorithm

```python
def remediate(files, max_passes=5):
    prev_count = float("inf")

    for pass_num in range(1, max_passes + 1):
        violations = scan(files)
        fixable = [v for v in violations if is_finding_resolvable(v, registry)]

        if not fixable:
            break  # nothing left to fix deterministically

        for v in fixable:
            content = read_file(v["file"])
            result = registry.apply(v["rule_id"], content, v)
            if result.applied:
                write_file(v["file"], result.content)

        # Re-scan to check progress
        new_violations = scan(files)
        new_count = len(new_violations)

        if new_count >= prev_count:
            # Oscillation or no progress — bail
            break

        prev_count = new_count

        if new_count == 0:
            break  # fully converged

    # After deterministic passes, escalate remaining to AI (if available)
    remaining = scan(files)
    non_fixable = [v for v in remaining if not is_finding_resolvable(v, registry)]
    ai_results = escalate_to_ai(non_fixable)  # no-op if AI unavailable

    return FixReport(
        passes=pass_num,
        fixed=prev_initial_count - len(remaining),
        remaining=remaining,
        ai_proposed=ai_results,
    )
```

### Oscillation Detection

An oscillation occurs when a fix introduces a new violation that triggers another fix that re-introduces the original. Detection is simple: if the violation count does not decrease after a pass, stop. The `max_passes` parameter (default 5) provides a hard ceiling.

### Convergence Report

```python
@dataclass
class FixReport:
    passes: int                     # number of convergence passes executed
    fixed: int                      # violations resolved by transforms
    remaining: list[dict]           # violations still present
    ai_proposed: list[dict]         # AI-suggested patches (pending review)
    oscillation_detected: bool      # True if loop bailed due to no progress
```

## gRPC Contract

### New `Fix` RPC on Primary

```protobuf
service Primary {
  rpc Scan(ScanRequest) returns (ScanResponse);
  rpc Format(FormatRequest) returns (FormatResponse);
  rpc Fix(FixRequest) returns (FixResponse);            // new
  rpc Health(HealthRequest) returns (HealthResponse);
}

message FixRequest {
  string project_root = 1;
  repeated File files = 2;
  FixOptions options = 3;
}

message FixOptions {
  int32 max_passes = 1;            // default 5
  bool no_ai = 2;                  // skip AI escalation
  bool auto_apply_ai = 3;          // apply AI patches without prompting
  float min_confidence = 4;        // AI confidence threshold (default 0.0)
  string ansible_core_version = 5;
  repeated string collection_specs = 6;
}

message FixResponse {
  int32 passes = 1;
  repeated FileDiff applied_patches = 2;     // deterministic fixes applied
  repeated AIProposal ai_proposals = 3;      // AI-suggested patches
  repeated Violation remaining = 4;          // violations not resolved
  bool oscillation_detected = 5;
}

message AIProposal {
  Violation violation = 1;
  string suggested_code = 2;
  float confidence = 3;
  string reasoning = 4;
  string diff = 5;
}
```

### OpenLLM Service (Phase 3)

```protobuf
service OpenLLM {
  rpc Remediate(RemediateRequest) returns (RemediateResponse);
  rpc Health(HealthRequest) returns (HealthResponse);
}

message RemediateRequest {
  string rule_id = 1;
  string message = 2;
  string file_path = 3;
  int32 line = 4;
  string code_window = 5;
  string file_content = 6;
  string ansible_version = 7;
}

message RemediateResponse {
  string suggested_code = 1;
  float confidence = 2;
  string reasoning = 3;
  bool applicable = 4;
}
```

## Container Topology (with Remediation)

```
┌────────────────────────────── apme-pod ──────────────────────────────────┐
│                                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Primary  │  │  Native  │  │   OPA    │  │ Ansible  │  │ Gitleaks │  │
│  │  :50051  │  │  :50055  │  │  :50054  │  │  :50053  │  │  :50056  │  │
│  │          │  │          │  │          │  │          │  │          │  │
│  │ engine + │  │ Python   │  │ OPA bin  │  │ ansible- │  │ gitleaks │  │
│  │ orchestr │  │ rules on │  │ + gRPC   │  │ core     │  │ + gRPC   │  │
│  │ remediat │  │ scandata │  │ wrapper  │  │ venvs    │  │ wrapper  │  │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│       │                                                                  │
│       │ gRPC (optional)                                                  │
│       ▼                                                                  │
│  ┌──────────┐                                                            │
│  │ OpenLLM  │  Phase 3 — AI escalation                                   │
│  │  :50057  │  bring-your-own-LLM provider                               │
│  └──────────┘                                                            │
│                                                                          │
│  ┌──────────────────────────────────────────┐                            │
│  │         Cache Maintainer :50052          │                            │
│  └──────────────────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────────────┘
```

The remediation engine lives inside Primary. It reuses Primary's existing scan pipeline and adds the transform → re-scan convergence loop. AI escalation is a gRPC call to the optional OpenLLM container.

## CLI Integration

### `apme-scan fix`

```
apme-scan fix [target] [options]

Options:
  --apply              Write fixes in place (without this, show diffs only)
  --check              Exit 1 if any fixes would be applied (CI mode)
  --no-ai              Skip AI escalation; deterministic fixes only
  --auto               Apply AI patches without prompting
  --min-confidence N   AI confidence threshold (default: 0.0)
  --max-passes N       Max convergence passes (default: 5)
  --exclude PATTERN    Glob patterns to skip
```

### Output

```
Phase 1: Formatting... 3 file(s) reformatted
Phase 2: Idempotency check... Passed
Phase 3: Scanning... 42 violation(s)
Phase 4: Remediating...
  Pass 1: 28 fixable → applied 26, 2 failed
  Pass 2: 4 fixable → applied 4
  Pass 3: 0 fixable → converged
Phase 5: AI escalation... 12 remaining → 8 proposals (skipped: --no-ai)
Phase 6: Summary
  Fixed:     30
  Remaining: 12 (manual review)
  AI proposed: 0 (--no-ai)
  Passes:    3
```

## Implementation Order

1. **Transform Registry + partition** — the data structures and registry pattern
2. **First transforms** — L021 (missing mode), L007 (shell→command), M001 (FQCN) as proof-of-concept
3. **Convergence loop** — scan → transform → re-scan loop with oscillation detection
4. **`Fix` RPC** — gRPC contract on Primary
5. **CLI `fix` integration** — wire the existing `_run_fix` stub to the real engine
6. **AI escalation** — OpenLLM gRPC client + prompt builder (Phase 3)
7. **Web UI remediation queue** — accept/reject AI proposals (Phase 4)
