"""Native rule L100: detect variable names that are Python or Ansible keywords."""

from dataclasses import dataclass
from typing import cast

from apme_engine.engine.models import (
    AnsibleRunContext,
    Rule,
    RuleResult,
    RuleScope,
    RunTargetType,
    Severity,
    YAMLDict,
)
from apme_engine.engine.models import (
    RuleTag as Tag,
)

PYTHON_KEYWORDS = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    }
)

ANSIBLE_KEYWORDS = frozenset(
    {
        "gather_facts",
        "hosts",
        "roles",
        "tasks",
        "handlers",
        "vars",
        "vars_files",
        "vars_prompt",
        "pre_tasks",
        "post_tasks",
        "become",
        "become_user",
        "become_method",
        "connection",
        "environment",
        "strategy",
        "serial",
        "collections",
        "module_defaults",
        "no_log",
        "tags",
        "when",
        "register",
        "changed_when",
        "failed_when",
        "loop",
        "with_items",
        "with_dict",
        "with_list",
        "until",
        "retries",
        "delay",
        "block",
        "rescue",
        "always",
        "notify",
        "listen",
        "ignore_errors",
        "ignore_unreachable",
        "any_errors_fatal",
        "check_mode",
        "diff",
        "throttle",
        "run_once",
        "debugger",
        "name",
        "action",
        "args",
    }
)

BLOCKED_NAMES = PYTHON_KEYWORDS | ANSIBLE_KEYWORDS


@dataclass
class VarNamingKeywordRule(Rule):
    """Rule for variable names not to be Python or Ansible keywords.

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

    rule_id: str = "L100"
    description: str = "Variable names must not be Python or Ansible keywords"
    enabled: bool = True
    name: str = "VarNamingKeyword"
    version: str = "v0.0.1"
    severity: str = Severity.MEDIUM
    tags: tuple[str, ...] = (Tag.VARIABLE,)
    scope: str = RuleScope.PLAYBOOK

    def match(self, ctx: AnsibleRunContext) -> bool:
        """Check if context has a task target.

        Args:
            ctx: AnsibleRunContext to evaluate.

        Returns:
            True if current target is a task.
        """
        if ctx.current is None:
            return False
        return bool(ctx.current.type == RunTargetType.Task)

    def process(self, ctx: AnsibleRunContext) -> RuleResult | None:
        """Check variable definitions for keyword collisions.

        Args:
            ctx: AnsibleRunContext to process.

        Returns:
            RuleResult with keyword_vars detail, or None.
        """
        task = ctx.current
        if task is None:
            return None
        spec = task.spec
        module = getattr(spec, "module", None) or ""
        module_opts = getattr(spec, "module_options", None) or {}

        keyword_vars: list[str] = []

        if module in ("ansible.builtin.set_fact", "set_fact") and isinstance(module_opts, dict):
            for key in module_opts:
                if key in ("cacheable",):
                    continue
                if key in BLOCKED_NAMES:
                    keyword_vars.append(key)

        if module in ("ansible.builtin.include_vars", "include_vars") and isinstance(module_opts, dict):
            var_name = module_opts.get("name")
            if var_name and var_name in BLOCKED_NAMES:
                keyword_vars.append(var_name)

        register = getattr(spec, "options", None) or {}
        if isinstance(register, dict):
            reg_name = register.get("register")
            if reg_name and reg_name in BLOCKED_NAMES:
                keyword_vars.append(str(reg_name))

        verdict = len(keyword_vars) > 0
        detail: dict[str, object] = {}
        if keyword_vars:
            detail["keyword_vars"] = keyword_vars
            detail["message"] = f"variable name(s) {', '.join(keyword_vars)} collide with Python/Ansible keywords"
        return RuleResult(
            verdict=verdict,
            detail=cast("YAMLDict | None", detail),
            file=cast("tuple[str | int, ...] | None", task.file_info()),
            rule=self.get_metadata(),
        )
