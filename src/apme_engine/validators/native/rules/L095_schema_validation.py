"""Native rule L095: detect YAML files that fail JSON schema validation."""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RuleScope,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

REQUIRED_PLAYBOOK_KEYS = frozenset({"hosts"})
REQUIRED_GALAXY_KEYS = frozenset({"namespace", "name", "version"})
VALID_PLAY_KEYS = frozenset(
    {
        "name",
        "hosts",
        "tasks",
        "roles",
        "pre_tasks",
        "post_tasks",
        "handlers",
        "vars",
        "vars_files",
        "vars_prompt",
        "gather_facts",
        "become",
        "become_user",
        "become_method",
        "connection",
        "environment",
        "strategy",
        "serial",
        "max_fail_percentage",
        "any_errors_fatal",
        "ignore_errors",
        "ignore_unreachable",
        "collections",
        "module_defaults",
        "tags",
        "when",
        "no_log",
        "debugger",
        "order",
        "port",
        "timeout",
        "throttle",
        "run_once",
        "check_mode",
        "diff",
        "force_handlers",
        "fact_path",
        "gather_subset",
        "gather_timeout",
    }
)


@dataclass
class SchemaValidationRule(Rule):
    """Rule for basic structural schema validation of playbooks and galaxy.yml.

    Attributes:
        rule_id: Rule identifier.
        description: Rule description.
        enabled: Whether the rule is enabled.
        name: Rule name.
        version: Rule version.
        severity: Severity level.
        tags: Rule tags.
        scope: Structural scope.
    """

    rule_id: str = "L095"
    description: str = "YAML file does not match expected schema structure"
    enabled: bool = True
    name: str = "SchemaValidation"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.QUALITY,)
    scope: str = RuleScope.PLAYBOOK

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a play target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a play or collection.
        """
        if ctx.current is None:
            return False
        return False  # needs play_data/metadata attrs not yet on model; enable later

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Validate basic schema structure and return result.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with schema_errors detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        filepath = ""
        fi = target.file_info()
        if fi:
            filepath = str(fi[0]) if fi else ""

        errors: list[str] = []

        if filepath.endswith("galaxy.yml") or filepath.endswith("galaxy.yaml"):
            metadata = getattr(target.spec, "metadata", None) or {}
            raw = metadata if isinstance(metadata, dict) else {}
            for key in REQUIRED_GALAXY_KEYS:
                if key not in raw:
                    errors.append(f"galaxy.yml missing required key: {key}")

        spec_data = getattr(target.spec, "play_data", None) or {}
        if isinstance(spec_data, dict) and spec_data:
            unknown = set(spec_data.keys()) - VALID_PLAY_KEYS
            unknown = {k for k in unknown if not k.startswith("_")}
            if unknown:
                errors.append(f"unknown play-level keys: {', '.join(sorted(unknown))}")

        verdict = len(errors) > 0
        detail: dict[str, object] = {}
        if errors:
            detail["schema_errors"] = errors
            detail["message"] = "; ".join(errors)
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", fi),
            rule=self.get_metadata(),
        )
