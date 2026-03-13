"""CLI subcommand to list all Risk Assessment Model metadata."""

import argparse

from ...risk_assessment_model import RAMClient
from ...scanner import config
from ...utils import show_all_ram_metadata


class RAMListCLI:
    """CLI subcommand to list all RAM metadata entries.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for RAM list."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Display all RAM metadata.

        Raises:
            ValueError: When action is not "list".

        """
        args = self.args
        assert args is not None
        action = args.action
        if action != "list":
            raise ValueError('RAMListCLI cannot be executed without "list" action')

        ram_client = RAMClient(root_dir=config.data_dir)

        all_ram_meta = ram_client.list_all_ram_metadata()
        show_all_ram_metadata(all_ram_meta)
