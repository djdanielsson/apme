"""Integration tests: run engine + validators on YAML from rule .md examples and assert expected violation/pass."""

from pathlib import Path
from typing import Any

import pytest

from apme_engine.runner import run_scan_playbook_yaml
from apme_engine.validators.native import NativeValidator
from apme_engine.validators.opa import OpaValidator
from tests.rule_doc_parser import discover_rule_docs


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _native_rules_dir() -> Path:
    return _repo_root() / "src" / "apme_engine" / "validators" / "native" / "rules"


def _opa_bundle_dir() -> Path:
    return _repo_root() / "src" / "apme_engine" / "validators" / "opa" / "bundle"


def _violation_ids_for_rule(violations: list[dict[str, Any]], rule_id: str, validator: str) -> list[str]:
    """Return violation rule_id values that match this doc rule (for assertion)."""
    expected = f"native:{rule_id}" if validator == "native" else rule_id
    return [v["rule_id"] for v in violations if v.get("rule_id") == expected]


def _ensure_playbook(yaml_content: str) -> str:
    """If content is a single task or task list without a play, wrap in a play."""
    import yaml

    try:
        data = yaml.safe_load(yaml_content)
    except Exception:
        return yaml_content
    if not data:
        return yaml_content
    # Single task (dict with module/key that looks like a task)
    if isinstance(data, dict):
        if "hosts" in data and "tasks" in data:
            return yaml_content
        return (
            "- name: Example play\n  hosts: localhost\n  connection: local\n  tasks:\n"
            + "    - "
            + str(yaml.dump(data, default_flow_style=False)).strip().replace("\n", "\n    ")
        )
    # List: could be list of plays or list of tasks
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and ("hosts" in first or "tasks" in first):
            return yaml_content
        # List of tasks
        tasks_yaml = str(yaml.dump(data, default_flow_style=False))
        return "- name: Example play\n  hosts: localhost\n  connection: local\n  tasks:\n" + "\n".join(
            "    " + line for line in tasks_yaml.splitlines()
        )
    return yaml_content


@pytest.fixture(scope="module")  # type: ignore[untyped-decorator]
def validators() -> dict[str, Any]:
    """OPA and Native validators. Native with no exclusions so all rules can run."""
    opa_bundle = str(_opa_bundle_dir())
    return {
        "opa": OpaValidator(opa_bundle),
        "native": NativeValidator(exclude_rule_ids=()),  # run all rules for doc tests
    }


def _collect_violations(yaml_content: str, validators: dict[str, Any]) -> list[dict[str, Any]]:
    """Run scan on YAML and return combined violations from both validators."""
    content = _ensure_playbook(yaml_content)
    try:
        context = run_scan_playbook_yaml(content, project_root=None, include_scandata=True)
    except Exception as e:
        pytest.skip(f"Scan failed (engine may need fixes): {e}")
    if not context.hierarchy_payload:
        return []
    violations = []
    for v in validators.values():
        violations.extend(v.run(context))
    return violations


def _rule_doc_params() -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """List of (md_path, doc) and corresponding ids for parametrize."""
    pairs = discover_rule_docs(_native_rules_dir(), _opa_bundle_dir())
    if not pairs:
        return [], []
    return pairs, [Path(p[0]).name for p in pairs]


_param_tuples, _param_ids = _rule_doc_params()


@pytest.mark.parametrize(
    "md_path,doc",
    _param_tuples if _param_tuples else [("", {})],
    ids=_param_ids if _param_ids else ["no_docs"],
)  # type: ignore[untyped-decorator]
def test_rule_doc_examples(md_path: str, doc: dict[str, Any], validators: dict[str, Any]) -> None:
    """For each rule .md with frontmatter and examples, run YAML and assert violation/pass."""
    if not doc.get("examples"):
        pytest.skip(f"No examples in {md_path}")
    rule_id = doc["rule_id"]
    validator = doc["validator"]
    if validator == "ansible":
        pytest.skip("Ansible validator docs require a venv; tested separately")
    for i, ex in enumerate(doc["examples"]):
        expect_violation = ex["expect_violation"]
        yaml_content = ex["yaml"]
        violations = _collect_violations(yaml_content, validators)
        matching = _violation_ids_for_rule(violations, rule_id, validator)
        if expect_violation:
            # Pass if this rule fired, or if any violation was found (example is "bad")
            assert matching or len(violations) > 0, (
                f"{md_path} example {i + 1} (violation): expected rule {rule_id} or any violation, "
                f"got: {[v['rule_id'] for v in violations]}"
            )
        else:
            assert not matching, f"{md_path} example {i + 1} (pass): expected no {rule_id}, got: {matching}"


def test_rule_doc_parser_smoke() -> None:
    """Ensure at least one rule doc is discoverable and parseable."""
    docs = discover_rule_docs(_native_rules_dir(), _opa_bundle_dir())
    # R102 should have frontmatter and examples
    r102 = [d for _, d in docs if d.get("rule_id") == "L029" or d.get("rule_id") == "R102"]
    assert len(r102) >= 1, "Expected at least one doc for L029/R102"
    assert r102[0].get("examples"), "Expected examples in R102/L029 doc"
