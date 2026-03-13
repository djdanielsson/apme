"""RAM (Risk Assessment Model) CLI subcommands: search, list, diff, generate, update, release."""

import sys

from .diff import RAMDiffCLI
from .generate import RAMGenerateCLI
from .list import RAMListCLI
from .release import RAMReleaseCLI
from .search import RAMSearchCLI
from .update import RAMUpdateCLI

ram_actions = ["search", "list", "diff", "generate", "update", "release"]


class RAMCLI:
    """CLI dispatcher for RAM (Risk Assessment Model) operations: search, list, diff, generate, update, release."""

    _cli: RAMSearchCLI | RAMListCLI | RAMDiffCLI | RAMGenerateCLI | RAMUpdateCLI | RAMReleaseCLI | None = None

    def __init__(self) -> None:
        """Parse sys.argv and instantiate the appropriate RAM subcommand CLI.

        Raises:
            ValueError: When no action is specified or action is not supported.

        """
        args = sys.argv
        if len(args) > 2:
            action = args[2]
            # "search" can be abbreviated
            if action not in ram_actions:
                action = "search"
                target_name = sys.argv[2]
                sys.argv[2] = action
                sys.argv.insert(3, target_name)

            if action == "search":
                self._cli = RAMSearchCLI()
            elif action == "list":
                self._cli = RAMListCLI()
            elif action == "diff":
                self._cli = RAMDiffCLI()
            elif action == "generate":
                self._cli = RAMGenerateCLI()
            elif action == "update":
                self._cli = RAMUpdateCLI()
            elif action == "release":
                self._cli = RAMReleaseCLI()
            else:
                raise ValueError(f"The action {action} is not supported")
        else:
            raise ValueError(f"An action must be specified; {ram_actions}")

    def run(self) -> None:
        """Execute the selected RAM subcommand."""
        if self._cli is not None:
            self._cli.run()
