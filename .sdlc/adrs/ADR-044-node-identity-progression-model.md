# ADR-044: Node Identity and Progression Model

## Status

Proposed

## Date

2026-03-27

## Context

APME's convergence loop (format → scan → transform → rescan, up to 5 passes) treats each scan as a stateless snapshot. The ARI engine, integrated per ADR-003, rebuilds the entire tree from scratch on every pass. No node carries identity across passes and no node records what happened to it over time.

This creates a two-dimensional problem that the current architecture models in only one dimension:

- **Vertical (hierarchy)**: The tree of plays, roles, blocks, tasks — well-modeled by ARI.
- **Horizontal (progression)**: How each node changes through formatting, Tier 1 transforms, AI proposals, and re-scans — not modeled at all.

### Where the gap hurts today

1. **Snippet accuracy**: Source snippets must show the file content at the moment a violation was found. The current `_attach_snippets` implementation uses `File` protos from the scan pipeline, which contain post-format content. Line numbers from validators reference the same post-format files. The snippets are internally consistent but show the user transformed code they didn't write, with no way to trace back to the original.

2. **Violation identity across passes**: Violations are matched between passes by `(rule_id, file, line)` tuples. After a Tier 1 transform shifts line numbers, this heuristic breaks. The remediation engine uses YAML paths as a more stable proxy (`NodeIndex`), but this is a workaround bolted onto a model that lacks first-class identity.

3. **Remediation attribution**: "Which transform fixed which violation?" is answered by inference (diff the violation sets between passes), not by direct tracking. There is no per-node change log.

4. **Parallel representations**: The same content exists in three forms — ARI's in-memory tree (for hierarchy/scandata), `StructuredFile` (ruamel.yaml, for Tier 1 transforms), and raw bytes on disk (for validator fan-out). These are synchronized by writing to disk and re-parsing, not by a shared identity model.

5. **Feedback quality**: When a user reports a false positive, we cannot include "this node was formatted on pass 0, violation V detected on pass 1, transform T attempted on pass 2, violation persisted on pass 3" because that history doesn't exist.

6. **Inherited property attribution**: ARI accumulates inherited properties (e.g. `become`, `variable_use`) from parent scopes (play, block) onto child tasks. Rules like R108 (privilege escalation) and L050 (variable naming) detect these inherited properties but attribute violations to the child task's start line — not to the scope where the property was defined. The result: a task with no `become:` keyword is highlighted for privilege escalation because it inherits `become` from its play; a task with no variables is flagged for variable naming because play-level vars like `MyAppVersion` are in scope. The user sees a highlighted line with no visible connection to the violation message. Without node identity and parent-child relationships, there is no way to attribute a violation to the defining scope ("inherited from play at line 3") rather than every inheriting task.

### The puzzle piece analogy

Consider 100 uniquely shaped puzzle pieces handed to 100 people who each make a change and document the color. At any point the puzzle can be reassembled. When everyone is done, every piece has a history of progression. The puzzle's integrity is preserved because identity is intrinsic to each piece, not derived from its position.

APME's current model is: disassemble the puzzle, throw away all the pieces, rebuild new pieces from the table surface, and hope the positions match.

### Lessons from ansible-core's object model

Ansible-core (`lib/ansible/playbook/`) maintains a proper hierarchy with explicit parent pointers — `Task._parent → Block`, `Block._parent → Block`, `Block._play → Play`, `Block._role → Role`, `Block._dep_chain → [Role]`. Property inheritance uses `FieldAttribute` descriptors whose `__get__` calls `_get_parent_attribute()`, which walks the full parent chain on every read. This means ansible-core always knows where an inherited value originates — it just never exposes that provenance as data.

Key patterns to adopt or avoid:

1. **`_get_parent_attribute()` is the `PropertyOrigin` blueprint.** The chain walk (Task → Block → parent Block → Role → dep chain → Play) preserves provenance at read time. ARI's scandata accumulation is equivalent to ansible-core's `squash()` — it materializes inherited values and discards the chain. ADR-044's model must never squash without recording origin.

2. **`_uuid` is process-local and ephemeral.** ansible-core assigns a random-ish ID at construction (`get_unique_id()` — MAC prefix + monotonic counter). It is not stable across runs or processes. ADR-044's YAML-path-based `NodeIdentity` is strictly more stable.

3. **Static vs dynamic includes create a partially-known tree.** `import_tasks` / `import_role` expand at parse time — fully resolved before execution. `include_tasks` / `include_role` remain as placeholder nodes until execution reaches them, and are host-divergent (different hosts may include different files). The effective tree is never globally complete. APME scans content structurally, not per-host, so dynamic includes are leaf nodes with unknown children.

4. **`when:` on static imports gates the expanded tasks, not the import itself.** The file is always loaded; the condition is attached as a parent and inherited by every expanded task. For dynamic includes, `when:` is evaluated first — if false, the file is never loaded.

5. **`NonInheritableFieldAttribute` distinguishes scope-sensitive from scope-insensitive properties.** `name` and `vars` are explicitly non-inheritable in ansible-core. This maps directly to ADR-043's scope-aware severity: only inheritable properties (become, ignore_errors) should escalate severity at broader scope; non-inheritable properties (name) should not.

### Decision drivers

- Remediation convergence requires tracking "same node, different state" across passes
- User-facing features (snippets, feedback, audit trails) need temporal context
- The formatter, scan engine, and remediation engine should share one model, not three
- ARI's parsing and hierarchy logic is valuable; its stateless snapshot model is not
- Inherited properties (become, vars) must be attributable to their defining scope, not every inheriting child
- ansible-core's `_get_parent_attribute()` chain demonstrates how to preserve provenance; ARI's accumulation model destroys it

## Decision

**We will build a purpose-built Node Identity and Progression Model that wraps ARI's parsing capabilities in an entity-with-history abstraction.**

Each meaningful unit of Ansible content (task, play, block, role reference, variable declaration) receives a stable identity at parse time. That identity persists through formatting, scanning, and remediation passes. Each node accumulates a progression log of state changes.

### Core concepts

**NodeIdentity**: A stable identifier derived from the node's structural position (YAML path) in the original, pre-format content. Identity is assigned once and never changes, even as line numbers shift.

**NodeState**: The content, violations, and metadata of a node at a specific point in time. Immutable once created.

**Progression**: An ordered sequence of `NodeState` entries for a single `NodeIdentity`, representing how that node evolved through the pipeline.

**ContentGraph**: The top-level container — a directed acyclic graph (DAG) of identified nodes with their progressions, parent-child relationships, and include edges. Replaces the current pattern of disconnected ARI tree + StructuredFile + file bytes. The graph is a DAG, not a tree, because roles and task files can be included by multiple parents — a role used by three playbooks exists once in the graph with three incoming include edges, not three copies.

**NodeScope**: Each node carries an ownership scope — `owned` (inside the scan boundary, eligible for violations and remediation) or `referenced` (resolved for context and inheritance, but violations are not reported and content is never modified). When scanning a collection, the collection's own roles and playbooks are `owned`; dependencies from Galaxy are `referenced`. The scan boundary is determined by what was submitted for analysis.

**PropertyOrigin**: When a node carries an inherited property (e.g. `become`, variables), the graph tracks the `NodeIdentity` of the defining scope — modeled after ansible-core's `_get_parent_attribute()` chain walk. Violations on inherited properties reference both the affected task and the origin node, enabling messages like "Privilege escalation inherited from play at site.yml:3" rather than attributing to the task's own line.

### Pipeline with progression

```
Phase 0 — Parse original files
  → Assign NodeIdentity to every node
  → Record NodeState[0]: original content, no violations

Phase 1 — Format
  → Apply formatter to each node's content
  → Record NodeState[1]: formatted content, diff from original

Phase 2..N — Scan + Transform (convergence)
  → ARI parse of current content (reusing its hierarchy/scandata logic)
  → Map ARI results back to identified nodes (by YAML path)
  → Record NodeState[N]: violations detected
  → Apply Tier 1 transforms
  → Record NodeState[N+1]: post-transform content, which violations resolved
  → Re-scan for convergence check
  → Continue until stable

Phase Final — Classification
  → Each node's progression is complete
  → Remaining violations carry their full history
  → Snippets are trivially extracted from any NodeState in the progression
```

### Relationship to ARI

ARI remains the parser and hierarchy builder. Its `run_scan` produces the hierarchy payload and scandata that validators consume. The change is:

- **Before**: ARI's output is the truth; files on disk are synchronized to match
- **After**: The `ContentGraph` is the truth; ARI is invoked as a service to parse content and produce hierarchy, but its output is mapped back onto identified nodes rather than used as the canonical model

This preserves ARI's valuable parsing logic while decoupling APME from ARI's stateless snapshot assumption.

## Alternatives Considered

### Alternative 1: Extend ARI with identity tracking

**Description**: Modify the vendored ARI engine internals to assign stable node IDs and carry them across `evaluate()` calls.

**Pros**:
- Single model (ARI's tree gains identity)
- No new abstraction layer

**Cons**:
- Deep coupling to ARI internals that were not designed for this
- ARI's `evaluate()` rebuilds trees from scratch by design — retrofitting identity means fighting its architecture
- Makes future ARI updates (porting upstream improvements) much harder
- ARI's node model (scandata, AnsibleRunContext) is optimized for rule evaluation, not lifecycle tracking

**Why not chosen**: Retrofitting identity into a stateless-by-design system creates more complexity than building a clean abstraction. Two workarounds for the same interface means redesign the interface.

### Alternative 2: Thin identity layer between ARI and remediation

**Description**: Keep ARI as-is. Build a `NodeRegistry` that maps YAML paths to stable IDs and maintains progression logs outside ARI. The existing `NodeIndex` is a primitive version of this.

**Pros**:
- Minimal changes to ARI
- Incremental adoption — can add identity tracking without rewriting the pipeline
- Lower initial effort

**Cons**:
- Two sources of truth (ARI's tree + the registry) that must be kept in sync
- YAML-path-based identity is fragile when transforms restructure content
- The three-representation problem (ARI tree, StructuredFile, file bytes) persists
- Every new feature must bridge between ARI's model and the registry

**Why not chosen**: This is the path of least resistance but accumulates the most long-term debt. It codifies the current workaround pattern rather than resolving the underlying model mismatch. Viable as a stepping stone but not as the target architecture.

### Alternative 3: Purpose-built model wrapping ARI (chosen)

**Description**: Build a `ContentGraph` that owns node identity and progression. Use ARI's parsing as an internal service for hierarchy building and rule evaluation, but map results back onto the graph rather than treating ARI's output as the canonical model.

**Pros**:
- Clean single source of truth for node identity, content, and history
- Snippets, attribution, and feedback are natural properties of the model
- Eliminates the three-representation synchronization problem
- ARI's parsing logic is preserved without coupling to its lifecycle assumptions
- Clearer design — the model matches the problem domain

**Cons**:
- Significant implementation effort
- Requires careful migration of existing pipeline code
- ARI integration becomes an adapter layer rather than direct use
- Risk of over-engineering if progression tracking proves less valuable than anticipated

## Consequences

### Positive

- Every violation carries a snippet from the exact content state when it was detected
- Violation identity is stable across passes — no more (file, line) heuristic matching
- Remediation attribution is explicit: "Transform T resolved violation V on node N at pass P"
- Feedback issues include full node progression (original → formatted → scanned → transformed)
- Single model serves parsing, validation, remediation, and reporting
- DAG structure prevents duplicate violations and duplicate remediation for shared content (roles used by multiple playbooks)
- Ownership borders cleanly separate "your code" from "your dependencies" without excluding dependencies from the analysis context
- Formatter changes become trackable events, not invisible preprocessing
- Inherited property violations reference their defining scope, not every inheriting child
- Plays and playbooks become first-class violation targets — an R108 "this play enables privilege escalation" fires once on the play node instead of once per inheriting task, significantly reducing noise
- UI can render violations hierarchically (Playbook > Play > Block > Task) with scope-appropriate snippets (play header for play-level violations, task body for task-level)

### Negative

- Large implementation effort spanning engine, remediation, and primary server
- ARI becomes an internal service with an adapter, adding indirection
- Migration must be carefully staged to avoid breaking the existing pipeline
- Additional memory for storing node progressions (bounded by pass count × node count)

### Neutral

- ARI's parsing and hierarchy-building code is unchanged — only its consumption model changes
- The gRPC contract between Primary and validators is unaffected (validators still receive `ValidateRequest`)
- The `Violation` proto gains a stable `node_id` field but remains backward-compatible

## Implementation Notes

### Phased adoption

1. **Phase A — NodeIdentity**: Assign stable IDs based on YAML path at initial parse. Thread IDs through violations. This alone fixes snippet accuracy and violation tracking. Can coexist with current pipeline.

2. **Phase B — Progression logging**: Record NodeState at each pipeline phase. Enables audit trails and enriched feedback. Requires changes to the convergence loop in `RemediationEngine`.

3. **Phase C — Unified model**: Replace the three-representation pattern (ARI tree + StructuredFile + file bytes) with `ContentGraph` as the single source of truth. Largest change, highest payoff.

### NodeIdentity derivation

```
<file-path>::<yaml-path>

Examples:
  site.yml::play[0]#task[3]
  roles/web/tasks/main.yml::task[0]
  site.yml::play[1]#block[0]#task[2]
```

YAML path is structural (based on node type and position), not content-dependent. It is assigned from the original file before any formatting and remains stable through content transforms that don't restructure the document.

### Snippet extraction with progression

```python
# At any point, a violation's snippet is trivially available:
node = content_graph.get(violation.node_id)
state = node.state_at(pass_number)  # or node.state_when_detected(violation)
snippet = state.content_lines(line - 10, line + 10)
```

### Scope-level violations and noise reduction

With node identity, rules that detect inherited properties can target the defining scope:

```python
# R108 today: fires on every task that inherits become (50 violations)
Violation(rule_id="R108", node_id="site.yml::play[0]#task[3]", line=30)
Violation(rule_id="R108", node_id="site.yml::play[0]#task[4]", line=37)
# ... 48 more

# R108 with ContentGraph: fires once on the play (1 violation)
Violation(
    rule_id="R108",
    node_id="site.yml::play[0]",
    line=3,
    message="Play enables privilege escalation (become_user: deployer)",
    affected_children=50,  # informational count
)
```

The UI renders play-level violations with the play header as the snippet (hosts, vars, become directives), giving the user immediate context for why the violation exists and where to fix it.

### Graph topology: DAG with ownership borders

The `ContentGraph` is a DAG, not a tree. Include/import directives create edges, not copies:

```
site.yml::play[0]
  ├── include_role: web         ──→ roles/web/tasks/main.yml (owned)
  └── include_role: common      ──→ roles/common/tasks/main.yml (owned)

deploy.yml::play[0]
  ├── include_role: web         ──→ roles/web/tasks/main.yml (same node)
  └── include_role: monitoring  ──→ galaxy.namespace.monitoring (referenced)
```

`roles/web` appears once in the graph with two incoming edges. A violation against it is reported once. A remediation fix is applied once. Both including playbooks benefit.

**Static imports** (`import_tasks`, `import_role`) are fully resolved at parse time — their content is materialized in the graph with the import directive as the include edge.

**Dynamic includes** (`include_tasks`, `include_role`) remain as leaf nodes with a `dynamic` edge type. Their children are unknown until execution and may vary per host. APME treats them as opaque scan boundaries — the include directive itself is scannable (rule L054 checks for missing files), but the included content is not part of the static graph.

**Ownership borders** determine the scan boundary:

- `owned`: content submitted for analysis. Violations reported, remediation applied, progression tracked.
- `referenced`: resolved for context (so property inheritance and variable resolution work). Violations suppressed or surfaced as advisory ("your dependency has issues"). Content never modified.

The border is set by what's submitted: scanning a role in isolation makes the role `owned` and its dependencies `referenced`. Scanning a collection makes all sibling roles `owned`. This is a property of the scan session, not intrinsic to the node — the same role can be `owned` in one scan and `referenced` in another.

### Compatibility

- `NodeIndex` (current YAML-path lookup) evolves into `ContentGraph`
- `StructuredFile` (ruamel.yaml) becomes the serialization layer for `NodeState`, not a parallel model
- `_attach_snippets` is replaced by node-level state queries
- Validators are unaffected — they still receive `ValidateRequest` with files and hierarchy

## Related Decisions

- [ADR-003](ADR-003-vendor-ari-engine.md): ARI integration model — this ADR redefines how ARI's output is consumed
- [ADR-009](ADR-009-remediation-engine.md): Remediation engine — convergence loop gains identity-aware tracking
- [ADR-023](ADR-023-per-finding-classification.md): Per-finding classification — node identity strengthens per-finding resolution tracking
- [ADR-026](ADR-026-rule-scope-metadata.md): Rule scope metadata — scope becomes a property of identified nodes
- [ADR-036](ADR-036-two-pass-remediation-engine.md): Two-pass remediation — progression model naturally supports multi-pass

## References

- Conversation analysis of snippet accuracy issues (2026-03-27)
- Puzzle piece analogy for entity-with-history design
- ansible-core source analysis: `lib/ansible/playbook/base.py` (FieldAttribute descriptors, `_get_parent_attribute`, `squash`), `block.py` (parent chain walk), `task.py` (task inheritance), `attribute.py` (FieldAttribute vs NonInheritableFieldAttribute), `helpers.py` (static import vs dynamic include resolution), `play_iterator.py` (HostState, dynamic task splicing)

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-03-27 | Bradley A. Thornton | Initial proposal |
| 2026-03-27 | Bradley A. Thornton | Added inherited property attribution, scope-level violations |
| 2026-03-27 | Bradley A. Thornton | Added ansible-core lessons, DAG topology, ownership borders |
