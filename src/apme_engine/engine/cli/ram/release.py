"""CLI subcommand to release Risk Assessment Model data as a tar.gz archive."""

import argparse

from ...risk_assessment_model import RAMClient
from ...scanner import config


class RAMReleaseCLI:
    """CLI subcommand to export RAM KB files to a tar.gz archive.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for RAM release."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        parser.add_argument("-o", "--outfile", help="if execute release action, specify tar.gz file to store KB files")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Export RAM KB files to the specified tar.gz outfile.

        Raises:
            ValueError: When action is not "release" or --outfile is missing.

        """
        args = self.args
        assert args is not None
        action = args.action
        if action != "release":
            raise ValueError('RAMReleaseCLI cannot be executed without "release" action')

        if not args.outfile:
            raise ValueError(
                '"release" action cannot be executed without `--outfile` option. '
                'Please set "tar.gz" file name to export KB files.'
            )

        ram_client = RAMClient(root_dir=config.data_dir)
        ram_client.release(args.outfile)
