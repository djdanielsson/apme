"""CLI subcommand to diff Risk Assessment Model data between two versions."""

import argparse

from ...risk_assessment_model import RAMClient
from ...scanner import config
from ...utils import show_diffs


class RAMDiffCLI:
    """CLI subcommand to diff Risk Assessment Model data between two versions.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for RAM diff."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        parser.add_argument("target_name", help="target_name for the action")
        parser.add_argument("version1", help="version string of the target")
        parser.add_argument("version2", help="version string compared")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Show diffs between two RAM versions for the given target.

        Raises:
            ValueError: When action is not "diff".

        """
        args = self.args
        assert args is not None
        action = args.action
        if action != "diff":
            raise ValueError('RAMDiffCLI cannot be executed without "diff" action')

        ram_client = RAMClient(root_dir=config.data_dir)
        diffs = ram_client.diff(args.target_name, args.version1, args.version2)
        show_diffs(diffs)
