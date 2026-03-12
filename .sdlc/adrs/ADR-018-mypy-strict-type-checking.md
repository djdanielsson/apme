# ADR-018: mypy Strict Mode Type Checking

## Status

Accepted

## Date

2026-03

## Context

The APME codebase (~244 Python files) had no static type checking configured. Type hints were used inconsistently — some functions had annotations, most did not. Without enforcement, type mismatches, missing return types, and bare generic types (e.g., `dict` instead of `dict[str, Any]`) accumulated throughout the codebase.

Python's type system, when enforced via mypy in strict mode, catches entire categories of bugs at development time: attribute access on None, wrong argument types, missing return values, and incompatible assignments. These errors otherwise surface only at runtime, often in production.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| No type checking | Zero upfront cost | Bugs caught only at runtime |
| mypy basic mode | Low friction, catches obvious errors | Permits untyped functions, misses strict violations |
| mypy strict mode | Maximum coverage, catches all type errors | Significant upfront effort to annotate entire codebase |
| pyright / pytype | Alternative checkers with different trade-offs | Less ecosystem adoption, different configuration model |

## Decision

**Adopt mypy strict mode globally.** All Python source files (src/, tests/, scripts/) must pass `mypy --strict`. The check is enforced via the prek pre-commit hook and CI.

## Rationale

- Strict mode catches the widest range of type errors — no-untyped-def, type-arg, union-attr, attr-defined, assignment mismatches
- The upfront cost (~3,800 errors fixed) is a one-time investment; ongoing cost is near-zero since prek enforces compliance on every commit
- Protobuf generated files (src/apme/v1/*_pb2*.py) are excluded — they are machine-generated and not under our control
- Third-party libraries without type stubs (ruamel.yaml, ansible, jsonpickle, etc.) use `ignore_missing_imports` overrides
- Aligns with ADR-014 (prek hooks) and ADR-015 (CI enforcement) — mypy is another quality gate in the same pipeline

## Configuration

```toml
[tool.mypy]
strict = true
python_version = "3.10"
exclude = ["src/apme/v1/.*_pb2"]
```

Type stub packages added to dev dependencies: `mypy`, `types-protobuf`, `types-PyYAML`, `types-requests`, `types-tabulate`, `grpc-stubs`.

The mypy hook in `.pre-commit-config.yaml` runs with `pass_filenames: false` and checks `src/ tests/ scripts/` as a whole, ensuring the pyproject.toml configuration (excludes, overrides) is respected.

## Consequences

### Positive
- All functions have explicit parameter and return types
- Generic collections are parameterized (`dict[str, Any]`, `list[str]`, etc.)
- Optional/nullable values are explicitly typed and checked before access
- New code must be fully typed to pass prek — no regression possible
- IDE support (autocomplete, refactoring) is significantly improved

### Negative
- Some genuinely dynamic code (e.g., protobuf attribute access, sample annotators) requires targeted `# type: ignore` comments
- Third-party libraries without stubs need `ignore_missing_imports` overrides, reducing coverage at module boundaries

## Related Decisions

- ADR-014: Ruff linter and prek pre-commit hooks (established the prek pipeline)
- ADR-015: GitHub Actions CI with prek (enforces hooks in CI)
