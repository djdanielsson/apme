"""CLI subcommand to search Risk Assessment Model findings for a target."""

import argparse

from ...risk_assessment_model import RAMClient
from ...scanner import config
from ...utils import split_name_and_version


class RAMSearchCLI:
    """CLI subcommand to search RAM findings for a collection or role.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for RAM search."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        parser.add_argument("target_name", help="target_name for the action")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Search and print RAM findings for the target.

        Raises:
            ValueError: When action is not "search".

        """
        args = self.args
        assert args is not None
        action = args.action
        target_name = args.target_name
        if action != "search":
            raise ValueError('RAMSearchCLI cannot be executed without "search" action')

        ram_client = RAMClient(root_dir=config.data_dir)

        target_name, target_version = split_name_and_version(target_name)
        findings = ram_client.search_findings(target_name, target_version)
        if findings:
            print(findings.summary_txt)
