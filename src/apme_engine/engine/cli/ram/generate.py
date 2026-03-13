"""CLI subcommand to generate Risk Assessment Model data for collections and roles."""

import argparse

from ...ram_generator import RiskAssessmentModelGenerator as RAMGenerator


class RAMGenerateCLI:
    """CLI subcommand to generate RAM data from a target list file.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for RAM generate."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        parser.add_argument("-f", "--file", help='target list like "collection community.general"')
        parser.add_argument("-r", "--resume", help="line number to resume scanning")
        parser.add_argument("--serial", action="store_true", help="if True, do not parallelize ram generation")
        parser.add_argument("--no-module-spec", action="store_true", help="if True, ansible-doc is not used")
        parser.add_argument("--download-only", action="store_true", help="if True, just download the content")
        parser.add_argument(
            "--include-tests", action="store_true", help='if true, load test contents in "tests/integration/targets"'
        )
        parser.add_argument("--no-retry", action="store_true", help="if True, not retry failed items.")
        parser.add_argument("-o", "--out-dir", help="output directory for the rule evaluation result")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Run RAM generation for targets from the specified file.

        Raises:
            ValueError: When action is not "generate" or target list format is invalid.

        """
        args = self.args
        assert args is not None
        action = args.action
        if action != "generate":
            raise ValueError('RAMGenerateCLI cannot be executed without "generate" action')

        target_list = []
        with open(args.file) as file:
            for line in file:
                parts = line.replace("\n", "").split(" ")
                if len(parts) != 2:
                    raise ValueError(
                        'target list file must be lines of "<type> <name>" such as "collection community.general"'
                    )
                target_list.append((parts[0], parts[1]))

        resume = -1
        if args.resume:
            resume = int(args.resume)

        parallel = True
        if args.serial:
            parallel = False

        ram_generator = RAMGenerator(
            target_list=target_list,
            resume=resume,
            parallel=parallel,
            download_only=args.download_only,
            include_test_contents=args.include_tests,
            out_dir=args.out_dir,
            no_module_spec=args.no_module_spec,
            no_retry=args.no_retry,
        )
        ram_generator.run()
