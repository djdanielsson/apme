"""Suppress subcommand: manage violation suppressions in ``.apme/suppressions.yml`` (ADR-055)."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from apme_engine.cli._exit_codes import EXIT_ERROR
from apme_engine.cli._project_root import discover_project_root
from apme_engine.cli._suppressions import (
    Suppression,
    load_suppressions,
    write_suppressions,
)
from apme_engine.fingerprint import canonicalize_rule_id, compute_fingerprint


def run_suppress(args: argparse.Namespace) -> None:
    """Execute the suppress subcommand.

    Args:
        args: Parsed CLI arguments.
    """
    subcmd = getattr(args, "suppress_command", None)
    if subcmd == "add":
        _suppress_add(args)
    elif subcmd == "list":
        _suppress_list(args)
    elif subcmd == "remove":
        _suppress_remove(args)
    else:
        sys.stderr.write("Error: suppress requires a subcommand (add, list, remove)\n")
        sys.exit(EXIT_ERROR)


def _suppress_add(args: argparse.Namespace) -> None:
    """Add a suppression entry.

    Args:
        args: Parsed CLI arguments.
    """
    target = getattr(args, "target", ".")
    project_root = discover_project_root(target)

    rule_id = canonicalize_rule_id(args.rule_id)
    mode = getattr(args, "mode", "full") or "full"
    reason = getattr(args, "reason", "") or ""
    original_yaml = getattr(args, "original_yaml", None) or ""
    module_fqcn = getattr(args, "module_fqcn", None) or ""
    fingerprint_arg = getattr(args, "fingerprint", None)

    if fingerprint_arg:
        fingerprint_arg = fingerprint_arg.strip().lower()
        if len(fingerprint_arg) != 64 or not all(c in "0123456789abcdef" for c in fingerprint_arg):
            sys.stderr.write(
                "Error: --fingerprint must be a 64-character hex SHA-256 digest\n",
            )
            sys.exit(EXIT_ERROR)
        fp = fingerprint_arg
    else:
        if mode == "full" and not original_yaml:
            sys.stderr.write(
                "Error: --original-yaml is required for 'full' mode (or provide --fingerprint directly)\n",
            )
            sys.exit(EXIT_ERROR)
        if mode == "rule_module" and not module_fqcn:
            sys.stderr.write("Error: --module-fqcn is required for 'rule_module' mode\n")
            sys.exit(EXIT_ERROR)
        fp = compute_fingerprint(rule_id, original_yaml, mode=mode, module_fqcn=module_fqcn)

    existing = load_suppressions(project_root)

    for s in existing:
        if s.fingerprint == fp:
            sys.stderr.write(f"Suppression already exists for fingerprint {fp[:12]}...\n")
            return

    new_entry = Suppression(
        fingerprint=fp,
        rule_id=rule_id,
        mode=mode,
        reason=reason,
        created=date.today().isoformat(),
    )
    existing.append(new_entry)
    write_suppressions(project_root, existing)
    sys.stdout.write(f"Added suppression: {rule_id} [{mode}] fingerprint={fp[:12]}...\n")


def _suppress_list(args: argparse.Namespace) -> None:
    """List all suppression entries.

    Args:
        args: Parsed CLI arguments.
    """
    target = getattr(args, "target", ".")
    project_root = discover_project_root(target)
    suppressions = load_suppressions(project_root)

    if not suppressions:
        sys.stdout.write("No suppressions configured.\n")
        return

    for s in suppressions:
        mode_tag = f" [{s.mode}]" if s.mode != "full" else ""
        reason_tag = f" — {s.reason}" if s.reason else ""
        sys.stdout.write(f"  {s.rule_id}{mode_tag}  {s.fingerprint[:16]}...{reason_tag}\n")

    sys.stdout.write(f"\n{len(suppressions)} suppression(s) total.\n")


def _suppress_remove(args: argparse.Namespace) -> None:
    """Remove a suppression entry by fingerprint prefix.

    Args:
        args: Parsed CLI arguments.
    """
    target = getattr(args, "target", ".")
    project_root = discover_project_root(target)
    suppressions = load_suppressions(project_root)
    fp_prefix = args.fingerprint.strip().lower()

    matches = [s for s in suppressions if s.fingerprint.startswith(fp_prefix)]

    if not matches:
        sys.stderr.write(f"No suppression found matching fingerprint prefix {fp_prefix!r}\n")
        sys.exit(EXIT_ERROR)

    if len(matches) > 1:
        sys.stderr.write(
            f"Ambiguous: {len(matches)} suppressions match prefix {fp_prefix!r}. Provide a longer prefix.\n",
        )
        sys.exit(EXIT_ERROR)

    remaining = [s for s in suppressions if s.fingerprint != matches[0].fingerprint]
    write_suppressions(project_root, remaining)
    sys.stdout.write(f"Removed suppression: {matches[0].rule_id} {matches[0].fingerprint[:16]}...\n")


def register_suppress_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    global_opts: argparse.ArgumentParser,
) -> None:
    """Register the suppress subcommand on the CLI parser.

    Args:
        subparsers: Subparsers action from the main argument parser.
        global_opts: Parent parser with shared global options.
    """
    suppress_p = subparsers.add_parser(
        "suppress",
        parents=[global_opts],
        help="Manage violation suppressions (.apme/suppressions.yml)",
    )
    suppress_sub = suppress_p.add_subparsers(dest="suppress_command", required=True)

    # ── suppress add ──
    add_p = suppress_sub.add_parser("add", help="Add a suppression entry")
    add_p.add_argument("--rule-id", required=True, help="Rule ID to suppress (e.g. L046)")
    add_p.add_argument(
        "--fingerprint",
        default=None,
        help="Pre-computed fingerprint hash (skips computation)",
    )
    add_p.add_argument(
        "--original-yaml",
        default=None,
        help="Original YAML content to fingerprint (for 'full' mode)",
    )
    add_p.add_argument(
        "--module-fqcn",
        default=None,
        help="Module FQCN (for 'rule_module' mode)",
    )
    add_p.add_argument(
        "--mode",
        default="full",
        choices=["full", "rule_module", "rule_only"],
        help="Fingerprint granularity (default: full)",
    )
    add_p.add_argument("--reason", default="", help="Justification for the suppression")
    add_p.add_argument("target", nargs="?", default=".", help="Project root")

    # ── suppress list ──
    list_p = suppress_sub.add_parser("list", help="List all suppressions")
    list_p.add_argument("target", nargs="?", default=".", help="Project root")

    # ── suppress remove ──
    rm_p = suppress_sub.add_parser("remove", help="Remove a suppression by fingerprint prefix")
    rm_p.add_argument("fingerprint", help="Fingerprint prefix (at least 8 chars recommended)")
    rm_p.add_argument("target", nargs="?", default=".", help="Project root")
