"""CLI package for APME engine: ARI scanner and RAM management commands."""

import argparse
import json
import os

from .. import logger
from ..finder import get_yml_list, list_scan_target, update_the_yaml_target
from ..scanner import ARIScanner, config
from ..utils import (
    get_collection_metadata,
    get_role_metadata,
    is_local_path,
    is_url,
    split_name_and_version,
)

__all__ = ["ARICLI", "RAMCLI", "logger"]


class ARICLI:
    """CLI for ARI (Ansible Rule Inspector) scanning of projects, roles, collections, playbooks, and taskfiles.

    Attributes:
        args: Parsed command-line arguments.

    """

    args: argparse.Namespace | None = None

    def __init__(self) -> None:
        """Parse command-line arguments for ARI scan operations."""
        parser = argparse.ArgumentParser(description="TODO")
        parser.add_argument(
            "-s",
            "--save",
            action="store_true",
            help="enable file save under ARI_DATA_DIR (default=/tmp/ari-data)",
        )
        parser.add_argument(
            "target_type", help="Content type", choices={"project", "role", "collection", "playbook", "taskfile"}
        )
        parser.add_argument("target_name", help="Name")
        parser.add_argument(
            "--playbook-only",
            action="store_true",
            help="if true, don't load playbooks/roles arround the specified playbook",
        )
        parser.add_argument(
            "--taskfile-only",
            action="store_true",
            help="if true, don't load playbooks/roles arround the specified taskfile",
        )
        parser.add_argument(
            "--skip-isolated-taskfiles",
            action="store_true",
            help="if true, skip isolated (not imported/included) taskfiles from roles",
        )
        parser.add_argument(
            "--skip-install", action="store_true", help="if true, skip install for the specified target"
        )
        parser.add_argument(
            "--dependency-dir", nargs="?", help="path to a directory that have dependencies for the target"
        )
        parser.add_argument("--collection-name", nargs="?", help="if provided, use it as a collection name")
        parser.add_argument("--role-name", nargs="?", help="if provided, use it as a role name")
        parser.add_argument(
            "--source", help="source server name in ansible config file (if empty, use public ansible galaxy)"
        )
        parser.add_argument(
            "--without-ram", action="store_true", help="if true, RAM data is not used and not even updated"
        )
        parser.add_argument("--read-only-ram", action="store_true", help="if true, RAM data is used but not updated")
        parser.add_argument(
            "--read-ram-for-dependency", action="store_true", help="if true, RAM data is used only for dependency"
        )
        parser.add_argument(
            "--update-ram",
            action="store_true",
            help="if true, RAM data is not used for scan but updated with the scan result",
        )
        parser.add_argument(
            "--include-tests", action="store_true", help='if true, load test contents in "tests/integration/targets"'
        )
        parser.add_argument("--silent", action="store_true", help='if true, do not print anything"')
        parser.add_argument(
            "--objects", action="store_true", help="if true, output objects.json to the output directory"
        )
        parser.add_argument(
            "--show-all", action="store_true", help="if true, show findings even if missing dependencies are found"
        )
        parser.add_argument("--json", help="if specified, show findings in json format")
        parser.add_argument("--yaml", help="if specified, show findings in yaml format")
        parser.add_argument(
            "--save-only-rule-result",
            action="store_true",
            help="if true, save only rule results and remove node details to reduce result file size",
        )
        parser.add_argument(
            "--scan-per-target",
            action="store_true",
            help="if true, do scanning per playbook, role or taskfile (this reduces memory usage while scanning)",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="if true, fix the scanned playbook after performing the inpline replace with ARI suggestions",
        )
        parser.add_argument(
            "--task-num-threshold",
            default="100",
            help=(
                "A threshold number to give up scanning a file where the number of tasks exceeds this (default to 100)"
            ),
        )
        parser.add_argument("-o", "--out-dir", help="output directory for the rule evaluation result")
        parser.add_argument(
            "-r",
            "--rules-dir",
            help=f"specify custom rule directories. use `-R` instead to ignore default rules in {config.rules_dir}",
        )
        parser.add_argument(
            "-R", "--rules-dir-without-default", help="specify custom rule directories and ignore default rules"
        )
        args = parser.parse_args()
        self.args = args

    def run(self) -> None:
        """Execute the ARI scan based on parsed arguments."""
        args = self.args
        assert args is not None
        print("ARI args: ", args.target_name)
        target_name = args.target_name
        target_version = ""
        if args.target_type in ["collection", "role"]:
            target_name, target_version = split_name_and_version(target_name)

        collection_name = ""
        role_name = ""
        if args.collection_name:
            collection_name = args.collection_name

        if args.role_name:
            role_name = args.role_name

        is_local = False
        if args.target_type in ["collection", "role"] and is_local_path(target_name):
            is_local = True
        if args.target_type in ["project", "playbook", "taskfile"] and not is_url(target_name):
            is_local = True

        if is_local and not collection_name and not role_name:
            coll_meta = get_collection_metadata(target_name)
            if coll_meta and isinstance(coll_meta, dict):
                coll_info = coll_meta.get("collection_info") or {}
                if isinstance(coll_info, dict):
                    _namespace = str(coll_info.get("namespace", ""))
                    _name = str(coll_info.get("name", ""))
                    collection_name = f"{_namespace}.{_name}"

            role_meta = get_role_metadata(target_name)
            if role_meta and isinstance(role_meta, dict):
                galaxy_info = role_meta.get("galaxy_info") or {}
                if isinstance(galaxy_info, dict):
                    role_name = str(galaxy_info.get("role_name", ""))

        rules_dir = config.rules_dir
        if args.rules_dir_without_default:
            rules_dir = args.rules_dir_without_default
        elif args.rules_dir:
            rules_dir = args.rules_dir + ":" + config.rules_dir

        silent = args.silent
        pretty = False
        output_format = ""
        if args.json or args.yaml:
            silent = True
            pretty = True
            if args.json:
                output_format = "json"
            elif args.yaml:
                output_format = "yaml"

        read_ram = True
        write_ram = True
        read_ram_for_dependency = False
        if args.without_ram:
            read_ram = False
            write_ram = False
        elif args.read_only_ram:
            read_ram = True
            write_ram = False
        elif args.update_ram:
            read_ram = False
            write_ram = True
        elif args.read_ram_for_dependency or args.include_tests:
            read_ram_for_dependency = True
            read_ram = False
            write_ram = False
        load_all_taskfiles = True
        if args.skip_isolated_taskfiles:
            load_all_taskfiles = False
        save_only_rule_result = False
        if args.save_only_rule_result:
            save_only_rule_result = True

        c = ARIScanner(
            root_dir=config.data_dir,
            rules_dir=rules_dir,
            do_save=args.save,
            read_ram=read_ram,
            write_ram=write_ram,
            read_ram_for_dependency=read_ram_for_dependency,
            show_all=args.show_all,
            silent=silent,
            pretty=pretty,
            output_format=output_format,
        )

        if args.scan_per_target:
            c.silent = True
            task_num_threshold = int(args.task_num_threshold)
            print("Listing scan targets (This might take several minutes for a large proejct)")
            targets = list_scan_target(root_dir=target_name, task_num_threshold=task_num_threshold)
            print("Start scanning")
            total = len(targets)
            file_list: dict[str, list[str]] = {"playbook": [], "role": [], "taskfile": []}
            for i, target_info in enumerate(targets):
                fpath = str(target_info.get("filepath", ""))
                fpath_from_root = str(target_info.get("path_from_root", ""))
                scan_type = str(target_info.get("scan_type", ""))
                count_in_type = len(file_list.get(scan_type, []))
                print(f"\r[{i + 1}/{total}] {scan_type} {fpath_from_root}                 ", end="")
                out_dir = os.path.join(args.out_dir, f"{scan_type}s", str(count_in_type))
                c.evaluate(
                    type=scan_type,
                    name=fpath,
                    target_path=fpath,
                    version=target_version,
                    install_dependencies=False,
                    dependency_dir=args.dependency_dir,
                    collection_name=collection_name,
                    role_name=role_name,
                    source_repository=args.source,
                    playbook_only=True,
                    taskfile_only=True,
                    include_test_contents=args.include_tests,
                    load_all_taskfiles=load_all_taskfiles,
                    save_only_rule_result=save_only_rule_result,
                    objects=args.objects,
                    out_dir=out_dir,
                )
                if scan_type in file_list:
                    file_list[scan_type].append(fpath_from_root)
            print("")
            for scan_type, list_per_type in file_list.items():
                index_data = {}
                if not list_per_type:
                    continue
                for i, fpath in enumerate(list_per_type):
                    index_data[i] = fpath
                list_file_path = os.path.join(args.out_dir, f"{scan_type}s", "index.json")
                logger.debug("list_file_path: ", list_file_path)
                with open(list_file_path, "w") as file:
                    json.dump(index_data, file)
                if args.fix:
                    for each in index_data:
                        ari_suggestion_file_path = os.path.join(
                            args.out_dir, f"{scan_type}s", str(each), "rule_result.json"
                        )
                        logger.debug("ARI suggestion file path: %s", ari_suggestion_file_path)
                        with open(ari_suggestion_file_path) as f:
                            ari_suggestion_data = json.load(f)
                            targets = ari_suggestion_data["targets"]
                            for i in reversed(range(len(targets))):
                                logger.debug("Nodes dir number: %s", i)
                                nodes = targets[i]["nodes"]
                                line_number_list: list[str] = []
                                mutated_yaml_list: list[str] = []
                                target_file_path = ""
                                temp_file_path = ""
                                for j in range(1, len(nodes)):
                                    node_rules = nodes[j]["rules"]
                                    for k in reversed(
                                        range(len(node_rules))
                                    ):  # loop through from rule 11, as that has the mutation
                                        w007_rule = node_rules[k]
                                        if (w007_rule["rule"]["rule_id"]).lower() == "w007":
                                            if not w007_rule.get("verdict") and w007_rule:
                                                break
                                            mutated_yaml = w007_rule["detail"]["mutated_yaml"]
                                            if mutated_yaml == "":
                                                break
                                            temp_data = index_data[each]
                                            if w007_rule["file"][0] not in temp_data:
                                                target_file_path = os.path.join(
                                                    args.target_name, temp_data, w007_rule["file"][0]
                                                )
                                                if temp_file_path != "" and target_file_path != temp_file_path:
                                                    update_the_yaml_target(
                                                        target_file_path, line_number_list, mutated_yaml_list
                                                    )
                                                    line_number_list = []
                                                    mutated_yaml_list = []
                                                mutated_yaml_list.append(mutated_yaml)
                                                temp_file_path = target_file_path
                                            else:
                                                target_file_path = os.path.join(args.target_name, temp_data)
                                                if temp_file_path != "" and target_file_path != temp_file_path:
                                                    update_the_yaml_target(
                                                        target_file_path, line_number_list, mutated_yaml_list
                                                    )
                                                    line_number_list = []
                                                    mutated_yaml_list = []
                                                mutated_yaml_list.append(mutated_yaml)
                                                temp_file_path = target_file_path
                                            line_number = w007_rule["file"][1]
                                            if isinstance(line_number, (list, tuple)) and len(line_number) >= 2:
                                                ln_str = f"{line_number[0]}-{line_number[1]}"
                                            elif isinstance(line_number, int):
                                                ln_str = f"{line_number}-{line_number}"
                                            else:
                                                ln_str = str(line_number)
                                            line_number_list.append(ln_str)
                                            break  # w007 rule with mutated yaml is processed, breaking out of iteration
                                try:
                                    if target_file_path == "" or not mutated_yaml_list or not line_number_list:
                                        continue
                                    update_the_yaml_target(target_file_path, line_number_list, mutated_yaml_list)
                                except Exception as ex:
                                    logger.warning("ARI inline replace mutation failed with exception: %s", ex)
        else:
            if not silent and not pretty:
                print("Start preparing dependencies")
            root_install = not args.skip_install
            if not silent and not pretty:
                print("Start scanning")
            _yml_list = get_yml_list(target_name)
            yaml_label_list = [(x["filepath"], x["label"], x["role_info"]) for x in _yml_list]
            c.evaluate(
                type=args.target_type,
                name=target_name,
                version=target_version,
                install_dependencies=root_install,
                dependency_dir=args.dependency_dir,
                collection_name=collection_name,
                role_name=role_name,
                source_repository=args.source,
                playbook_only=args.playbook_only,
                taskfile_only=args.taskfile_only,
                include_test_contents=args.include_tests,
                load_all_taskfiles=load_all_taskfiles,
                save_only_rule_result=save_only_rule_result,
                yaml_label_list=yaml_label_list,  # type: ignore[arg-type]
                objects=args.objects,
                out_dir=args.out_dir,
            )
