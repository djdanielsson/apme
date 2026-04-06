"""AbbenayProvider — default AIProvider implementation using abbenay_grpc.

This is the sole file in the codebase that imports abbenay_grpc.
Install with: pip install apme-engine[ai]
"""

from __future__ import annotations

import json
import logging
import os
from importlib.resources import files as pkg_files
from pathlib import Path

import yaml

from apme_engine.remediation.ai_context import AINodeContext
from apme_engine.remediation.ai_provider import AINodeFix, AISkipped

logger = logging.getLogger(__name__)

_BEST_PRACTICES: dict[str, list[str]] | None = None

RULE_CATEGORY_MAP: dict[str, str] = {
    "M001": "fqcn",
    "M002": "fqcn",
    "M003": "fqcn",
    "M004": "fqcn",
    "L007": "yaml_formatting",
    "L008": "yaml_formatting",
    "L009": "yaml_formatting",
    "M006": "module_usage",
    "M008": "module_usage",
    "M009": "module_usage",
    "L011": "naming",
    "L012": "naming",
    "L013": "naming",
    "L043": "jinja2",
    "L046": "jinja2",
}

NODE_PROMPT_TEMPLATE = """\
You are an Ansible remediation assistant. Fix the flagged issues in this
YAML task/block while following Ansible best practices.

## Violations

{violation_list}

## YAML to fix
```yaml
{yaml_lines}
```

{parent_context_section}

{sibling_context_section}

## Ansible Best Practices
{best_practices}

{feedback_section}

## Instructions

Return the COMPLETE corrected YAML for this task/block in "fixed_snippet".
Do NOT return line numbers — just the corrected YAML text.

Respond with ONLY this JSON (no markdown fences, no explanation outside JSON):
{{
  "fixed_snippet": "<the entire corrected YAML for this task/block>",
  "changes": [
    {{
      "rule_id": "<rule ID fixed>",
      "explanation": "<one-sentence explanation>",
      "confidence": 0.95
    }}
  ],
  "skipped": [
    {{
      "rule_id": "<rule ID that could not be fixed>",
      "reason": "<why this cannot be auto-fixed>",
      "suggestion": "<how the user can fix this manually>"
    }}
  ]
}}

Rules:
- CRITICAL: Fix ONLY the violations listed above. Do NOT make any other changes,
  improvements, or best-practice adjustments beyond what is required to resolve the
  listed violations. If a line is not related to a listed violation, preserve it
  exactly as-is — same quoting, same structure, same values.
- If none of the listed violations can be fixed, return the original snippet unchanged
  in fixed_snippet and put all violations in "skipped".
- fixed_snippet must contain the COMPLETE corrected YAML, not a partial diff
- Preserve YAML comments and exact indentation (2 spaces per level)
- Use FQCN for all modules (e.g., ansible.builtin.copy, not copy)
- Use YAML syntax for task arguments, not key=value
- Use true/false for booleans, not yes/no
- If you cannot fix a violation confidently, add it to "skipped" instead
- Every violation must appear in either "changes" or "skipped"
"""


def _build_node_prompt(context: AINodeContext) -> str:
    """Build LLM prompt from graph-derived node context.

    Args:
        context: ``AINodeContext`` with node YAML, violations, and graph context.

    Returns:
        Formatted prompt string.
    """
    violation_entries: list[str] = []
    for idx, v in enumerate(context.violations, 1):
        rule_id = str(v.get("rule_id", ""))
        message = str(v.get("message", ""))
        violation_entries.append(f"{idx}. [{rule_id}]: {message}")

    rule_ids = [str(v.get("rule_id", "")) for v in context.violations]
    best_practices = _get_best_practices_for_rules(rule_ids)

    parent_section = ""
    if context.parent_context:
        parent_section = f"## Inherited Context (from parent play/block)\n{context.parent_context}"

    sibling_section = ""
    if context.sibling_snippets:
        sibling_yaml = "\n---\n".join(context.sibling_snippets)
        sibling_section = f"## Surrounding Tasks (for awareness only — do NOT modify)\n```yaml\n{sibling_yaml}\n```"

    feedback_section = ""
    if context.feedback:
        feedback_section = (
            f"## Previous Attempt Feedback\n{context.feedback}\n\nPlease correct these issues in your new response."
        )

    return NODE_PROMPT_TEMPLATE.format(
        violation_list="\n".join(violation_entries),
        yaml_lines=context.yaml_lines,
        parent_context_section=parent_section,
        sibling_context_section=sibling_section,
        best_practices=best_practices,
        feedback_section=feedback_section,
    )


def _parse_node_response(
    response_text: str,
    original_snippet: str,
) -> AINodeFix | None:
    """Parse LLM response into an ``AINodeFix``.

    Args:
        response_text: Raw text response from the LLM.
        original_snippet: Original YAML text of the node.

    Returns:
        ``AINodeFix`` if the AI produced a valid change, else ``None``.
    """
    data = _extract_json_object(response_text)
    if data is None:
        logger.warning(
            "_parse_node_response: no JSON object found in response (response_length=%d)",
            len(response_text),
        )
        return None

    fixed_snippet = data.get("fixed_snippet")
    if not isinstance(fixed_snippet, str):
        skipped = _parse_skipped(data)
        if skipped:
            logger.info("AI node response has no fixed_snippet but %d skipped entries", len(skipped))
            return AINodeFix(fixed_snippet="", skipped=skipped)
        logger.warning("AI node response missing 'fixed_snippet' field")
        return None

    skipped = _parse_skipped(data)

    if fixed_snippet.strip() == original_snippet.strip():
        logger.info("AI returned unchanged snippet (%d skipped)", len(skipped))
        if skipped:
            return AINodeFix(fixed_snippet="", skipped=skipped)
        return None

    changes: list[object] = data.get("changes", [])
    rule_ids: list[str] = []
    explanations: list[str] = []
    confidences: list[float] = []
    for c in changes:
        if not isinstance(c, dict):
            continue
        rid = c.get("rule_id")
        if rid:
            rule_ids.append(str(rid))
        exp = c.get("explanation")
        if exp:
            explanations.append(str(exp))
        conf = c.get("confidence")
        if conf is not None:
            try:
                confidences.append(float(conf))
            except (TypeError, ValueError):
                logger.debug("Ignoring non-numeric confidence value from AI: %r", conf)

    return AINodeFix(
        fixed_snippet=fixed_snippet,
        rule_ids=rule_ids if rule_ids else ["ai-fix"],
        explanation="; ".join(explanations[:3]) if explanations else "AI-generated fix",
        confidence=sum(confidences) / len(confidences) if confidences else 0.85,
        skipped=skipped,
    )


def discover_abbenay() -> str | None:
    """Auto-discover Abbenay daemon address from runtime socket.

    Search order mirrors the daemon's path conventions (paths.ts):
      1. $XDG_RUNTIME_DIR/abbenay/daemon.sock
      2. /run/user/<uid>/abbenay/daemon.sock  (Linux without XDG)
      3. /tmp/abbenay/daemon.sock             (fallback)

    Returns:
        A 'unix://' address string, or None if no socket found.
    """
    candidates: list[Path] = []

    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidates.append(Path(xdg) / "abbenay" / "daemon.sock")

    uid = os.getuid()
    candidates.append(Path(f"/run/user/{uid}/abbenay/daemon.sock"))
    candidates.append(Path("/tmp/abbenay/daemon.sock"))

    for sock in candidates:
        if sock.exists():
            return f"unix://{sock}"
    return None


def _load_best_practices() -> dict[str, list[str]]:
    """Load the structured best practices mapping from the data package.

    Returns:
        Dict keyed by category with lists of guideline strings.
    """
    global _BEST_PRACTICES  # noqa: PLW0603
    if _BEST_PRACTICES is not None:
        return _BEST_PRACTICES

    data_dir = pkg_files("apme_engine") / "data"
    bp_path = data_dir / "ansible_best_practices.yml"
    raw = bp_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw)
    loaded.pop("_meta", None)
    _BEST_PRACTICES = loaded
    return _BEST_PRACTICES


def _get_best_practices_for_rules(rule_ids: list[str]) -> str:
    """Return formatted best practices for a set of rule categories.

    Args:
        rule_ids: List of APME rule IDs.

    Returns:
        Formatted string of relevant guidelines.
    """
    bp = _load_best_practices()
    universal = bp.get("universal", [])

    categories: set[str] = set()
    for rid in rule_ids:
        bare = rid.split(":")[-1] if ":" in rid else rid
        cat = RULE_CATEGORY_MAP.get(bare, "")
        if cat:
            categories.add(cat)

    specific: list[str] = []
    for cat in sorted(categories):
        specific.extend(bp.get(cat, []))

    combined = universal + specific
    if not combined:
        return "No specific guidelines available."
    seen: set[str] = set()
    deduped: list[str] = []
    for g in combined:
        if g not in seen:
            seen.add(g)
            deduped.append(g)
    return "\n".join(f"- {g}" for g in deduped)


def _extract_json_object(text: str) -> dict | None:  # type: ignore[type-arg]
    """Extract the first top-level JSON object from *text*.

    LLMs sometimes emit reasoning text before or after the JSON payload,
    or wrap the response in markdown fences.  This function strips all of
    that and returns the parsed ``dict``, or ``None`` on failure.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed dict or None if no valid JSON object is found.
    """
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    brace_start = cleaned.find("{")
    if brace_start == -1:
        logger.warning(
            "No JSON object found in AI response (first 300 chars): %.300s",
            cleaned,
        )
        return None

    depth = 0
    in_string = False
    escape_next = False
    brace_end = -1

    for i in range(brace_start, len(cleaned)):
        ch = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                brace_end = i
                break

    if brace_end == -1:
        logger.warning(
            "Unterminated JSON object in AI response (first 300 chars): %.300s",
            cleaned,
        )
        return None

    json_str = cleaned[brace_start : brace_end + 1]
    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            if brace_start > 0:
                logger.debug(
                    "Stripped %d chars of preamble from AI response",
                    brace_start,
                )
            return data
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Extracted JSON region is invalid (first 300 chars): %.300s",
            json_str,
        )

    return None


def _parse_skipped(data: dict) -> list[AISkipped]:  # type: ignore[type-arg]
    """Extract skipped violations from the parsed LLM JSON.

    Args:
        data: Parsed JSON response dict.

    Returns:
        List of AISkipped objects (empty if none present).
    """
    raw = data.get("skipped")
    if not isinstance(raw, list):
        return []

    result: list[AISkipped] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rule_id = str(entry.get("rule_id", ""))
        line = entry.get("line", 0)
        reason = str(entry.get("reason", ""))
        suggestion = str(entry.get("suggestion", ""))
        if rule_id and (reason or suggestion):
            result.append(
                AISkipped(
                    rule_id=rule_id,
                    line=int(line) if line else 0,
                    reason=reason,
                    suggestion=suggestion,
                )
            )
    return result


class AbbenayProvider:
    """AIProvider implementation using the Abbenay daemon via abbenay_grpc.

    This is the sole file that imports abbenay_grpc. The import is
    deferred to __init__ so the core package works without it installed.
    """

    def __init__(
        self,
        addr: str,
        *,
        token: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize the Abbenay provider.

        Args:
            addr: Daemon address (e.g. 'unix:///run/user/1000/abbenay/daemon.sock').
            token: Optional consumer auth token for inline policy access.
            model: Optional default model (e.g. 'openai/gpt-4o').

        Raises:
            ImportError: If abbenay_grpc is not installed.
        """
        try:
            from abbenay_grpc import AbbenayClient  # noqa: PLC0415
        except ImportError:
            raise ImportError(
                "AI escalation requires the 'ai' extra.\nInstall with: pip install apme-engine[ai]"
            ) from None

        if addr.startswith("unix://"):
            socket_path = addr.removeprefix("unix://")
            self._client: object = AbbenayClient(socket_path=socket_path)
        elif ":" in addr:
            host, _, port_str = addr.rpartition(":")
            self._client = AbbenayClient(host=host, port=int(port_str))
        else:
            self._client = AbbenayClient(host=addr)
        self._addr = addr
        self._token = token
        self._model = model
        self._AbbenayClient = AbbenayClient

    def _make_client(self) -> object:
        """Create a fresh AbbenayClient instance for the current event loop.

        Returns:
            New AbbenayClient bound to the current asyncio loop.
        """
        addr = self._addr
        if addr.startswith("unix://"):
            return self._AbbenayClient(socket_path=addr.removeprefix("unix://"))
        if ":" in addr:
            host, _, port_str = addr.rpartition(":")
            return self._AbbenayClient(host=host, port=int(port_str))
        return self._AbbenayClient(host=addr)

    async def preflight(self) -> bool:
        """Connect to the daemon and run a health check.

        Returns:
            True if the daemon is healthy, False otherwise.
        """
        try:
            self._client = self._make_client()
            await self._client.connect()  # type: ignore[attr-defined]
            result: bool = await self._client.health_check()  # type: ignore[attr-defined]
            return result
        except Exception:
            logger.exception("Abbenay health check failed")
            return False

    async def reconnect(self) -> None:
        """Recreate client and reconnect for the current event loop."""
        self._client = self._make_client()
        await self._client.connect()  # type: ignore[attr-defined]

    async def _chat_with_reconnect(
        self,
        model: str,
        prompt: str,
        policy: dict[str, object],
    ) -> str:
        """Call chat, reconnecting once on connection failure.

        Args:
            model: Model identifier.
            prompt: User prompt text.
            policy: Sampling/output policy dict.

        Returns:
            Concatenated response text from the model.

        Raises:
            Exception: If the chat call fails after one reconnect retry.
        """
        for attempt in range(2):
            try:
                response_text = ""
                async for chunk in self._client.chat(  # type: ignore[attr-defined]
                    model=model,
                    message=prompt,
                    policy=policy,
                    token=self._token,
                ):
                    if hasattr(chunk, "text") and chunk.text:
                        response_text += chunk.text
                return response_text
            except Exception:
                if attempt == 0:
                    logger.debug("Chat failed, reconnecting to Abbenay and retrying")
                    await self.reconnect()
                else:
                    raise
        return ""  # unreachable but satisfies mypy

    async def propose_node_fix(
        self,
        context: AINodeContext,
        *,
        model: str | None = None,
    ) -> AINodeFix | None:
        """Propose a fix for a single graph node using graph-derived context.

        Args:
            context: Graph-derived context bundle for this node.
            model: Optional model override.

        Returns:
            ``AINodeFix`` with corrected YAML, or ``None`` on failure.

        Raises:
            Exception: If the Abbenay API call fails (e.g. network, credits).
        """
        prompt = _build_node_prompt(context)
        effective_model = model or self._model

        policy: dict[str, object] = {
            "sampling": {"temperature": 0.0},
            "output": {
                "format": "json_only",
                "max_tokens": 8192,
            },
            "reliability": {
                "timeout": 60000,
            },
        }

        try:
            response_text = await self._chat_with_reconnect(
                effective_model or "",
                prompt,
                policy,
            )
        except Exception:
            logger.exception(
                "Abbenay node call failed for %d violations on %s",
                len(context.violations),
                context.node_id,
            )
            raise

        if not response_text.strip():
            return None

        logger.debug(
            "Abbenay node response (%d chars) for %s: %.500s",
            len(response_text),
            context.node_id,
            response_text,
        )
        return _parse_node_response(response_text, context.yaml_lines)
