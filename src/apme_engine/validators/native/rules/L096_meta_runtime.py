"""Native rule L096: detect invalid or missing requires_ansible in meta/runtime.yml."""

import re
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

_VERSION_SPEC = re.compile(r"^[><=!~]+\s*\d+\.\d+(\.\d+)?")


@dataclass
class MetaRuntimeRule(Rule):
    """Rule for requires_ansible in meta/runtime.yml to be valid.

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

    rule_id: str = "L096"
    description: str = "meta/runtime.yml requires_ansible must be a valid version specifier"
    enabled: bool = True
    name: str = "MetaRuntime"
    version: str = "v0.0.1"
    severity: str = Severity.HIGH
    tags: tuple[str, ...] = (Tag.DEPENDENCY,)
    scope: str = RuleScope.COLLECTION

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a collection target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a collection.
        """
        if ctx.current is None:
            return False
        return False  # no Collection target type yet; enable when engine supports it

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Validate requires_ansible in runtime.yml.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with detail, or None.
        """
        target = ctx.current
        if target is None:
            return None
        metadata = getattr(target.spec, "metadata", None) or {}
        runtime = metadata.get("runtime") if isinstance(metadata, dict) else None
        if not isinstance(runtime, dict):
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", target.file_info()),
                rule=self.get_metadata(),
            )
        requires = runtime.get("requires_ansible")
        if requires is None:
            return RuleResult(
                verdict=False,
                file=cast("tuple[str | int, ...] | None", target.file_info()),
                rule=self.get_metadata(),
            )
        req_str = str(requires).strip()
        valid = bool(_VERSION_SPEC.match(req_str))
        verdict = not valid
        detail: dict[str, object] = {}
        if verdict:
            detail["requires_ansible"] = req_str
            detail["message"] = "requires_ansible is not a valid version specifier"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", target.file_info()),
            rule=self.get_metadata(),
        )
