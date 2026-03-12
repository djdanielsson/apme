import argparse

from ...ram_generator import RiskAssessmentModelGenerator as RAMGenerator


class RAMUpdateCLI:
    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument("target_type", help="content type", choices={"ram"})
        parser.add_argument("action", help="action for RAM command or target_name of search action")
        parser.add_argument("-f", "--file", help='target list like "collection community.general"')
        parser.add_argument("-r", "--resume", help="line number to resume scanning")
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        args = self.args
        assert args is not None
        action = args.action
        if action != "update":
            raise ValueError('RAMUpdateCLI cannot be executed without "update" action')

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
        ram_generator = RAMGenerator(target_list, resume, update=True)
        ram_generator.run()
