from __future__ import annotations

import sys
from typing import Any

from .scanner import ARIScanner, Config

# ARI CLI (ARICLI, RAMCLI) not imported by default to avoid pulling in heavy deps on scanner import.
ARICLI: type[Any] | None = None
RAMCLI: type[Any] | None = None

ari_actions = ["project", "playbook", "collection", "role", "taskfile"]
ram_actions = ["ram"]

all_actions = ari_actions + ram_actions


def main() -> None:
    if len(sys.argv) == 1:
        print("Please specify one of the following operations of ari.")
        print("[operations]")
        print("   playbook     scan a playbook (e.g. `ari playbook path/to/playbook.yml` )")
        print("   collection   scan a collection (e.g. `ari collection collection.name` )")
        print("   role         scan a role (e.g. `ari role role.name` )")
        print("   project      scan a project (e.g. `ari project path/to/project`)")
        print("   taskfile     scan a taskfile (e.g. `ari taskfile path/to/taskfile.yml`)")
        print("   ram          operate the backend data (e.g. `ari ram generate -f input.txt`)")
        sys.exit()

    action = sys.argv[1]

    if action in ari_actions:
        from .cli import ARICLI as _ARICLI

        ari_cli = _ARICLI()
        ari_cli.run()
    elif action == "ram":
        from .cli.ram import RAMCLI as _RAMCLI

        ram_cli = _RAMCLI()
        ram_cli.run()
    else:
        print(f"The action {action} is not supported!", file=sys.stderr)
        sys.exit(1)


__all__ = ["ARIScanner", "Config", "models"]
