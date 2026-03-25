#!/usr/bin/env python3
"""Test AI prompt/response directly against Abbenay.

Builds a unit prompt for a sample unit from site.yml and sends it
to the Abbenay daemon, printing the full response for debugging.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from apme_engine.remediation.abbenay_provider import (  # noqa: E402
    _build_unit_prompt,
    _extract_json_object,
    _parse_unit_response,
    discover_abbenay,
)

SAMPLE_SNIPPET = """\
    - name: get the hostname
      shell: hostname
"""

SAMPLE_VIOLATIONS: list[dict[str, str | int | list[int] | bool | None]] = [
    {
        "rule_id": "L007",
        "line": 24,
        "message": "Tasks should use 'command' rather than 'shell' when no shell features are used.",
    },
    {
        "rule_id": "L013",
        "line": 24,
        "message": "Tasks that run commands should set a 'changed_when' condition.",
    },
    {
        "rule_id": "M001",
        "line": 24,
        "message": "Use FQCN for all modules (ansible.builtin.shell instead of shell).",
    },
]


async def test_prompt(model: str) -> None:
    """Send a unit prompt to Abbenay and print results.

    Args:
        model: LLM model identifier (e.g. ``openrouter/anthropic/claude-sonnet-4``).
    """
    import os

    from abbenay_grpc import AbbenayClient

    addr = os.environ.get("APME_ABBENAY_ADDR") or discover_abbenay() or "127.0.0.1:50057"
    print(f"Abbenay addr: {addr}")

    token = os.environ.get("APME_ABBENAY_TOKEN", "apme-dev-token")
    if ":" in addr and not addr.startswith("unix://"):
        host, _, port_str = addr.rpartition(":")
        client = AbbenayClient(host=host, port=int(port_str))
    else:
        client = AbbenayClient(socket_path=addr.removeprefix("unix://"))
    await client.connect()

    prompt = _build_unit_prompt(
        SAMPLE_VIOLATIONS,
        SAMPLE_SNIPPET,
        file_path="site.yml",
        line_start=23,
        line_end=24,
    )
    print("=" * 60)
    print("PROMPT:")
    print("=" * 60)
    print(prompt)
    print("=" * 60)

    policy: dict[str, object] = {
        "sampling": {"temperature": 0.0},
        "output": {"format": "json_only", "max_tokens": 8192},
        "reliability": {"timeout": 60000},
    }

    response_text = ""
    async for chunk in client.chat(
        model=model,
        message=prompt,
        policy=policy,
        token=token,
    ):
        if hasattr(chunk, "text") and chunk.text:
            response_text += chunk.text

    print("\nRAW RESPONSE:")
    print("=" * 60)
    print(response_text)
    print("=" * 60)

    data = _extract_json_object(response_text)
    if data:
        print("\nPARSED JSON:")
        print(json.dumps(data, indent=2))

        patches, skipped = _parse_unit_response(response_text, SAMPLE_SNIPPET, 23, 24)
        print(f"\nPatches: {len(patches) if patches else 0}")
        print(f"Skipped: {len(skipped)}")
        if patches:
            for p in patches:
                print(f"  [{p.rule_id}] L{p.line_start}-{p.line_end}: {p.explanation}")
        if skipped:
            for s in skipped:
                print(f"  SKIP [{s.rule_id}] L{s.line}: {s.reason}")
    else:
        print("\nFailed to extract JSON!")


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "openrouter/anthropic/claude-sonnet-4"
    asyncio.run(test_prompt(model))
