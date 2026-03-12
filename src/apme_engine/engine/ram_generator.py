from __future__ import annotations

import datetime
import json
import os
import threading
import time
import traceback

import joblib

from .scanner import ARIScanner, config


class RiskAssessmentModelGenerator:
    _queue: list[tuple[str, str]]
    _resume: int
    _update: bool
    _scanner: ARIScanner
    start: float | None = None

    def __init__(
        self,
        target_list: list[tuple[str, str]] | None = None,
        resume: int = -1,
        update: bool = False,
        parallel: bool = True,
        download_only: bool = False,
        include_test_contents: bool = False,
        out_dir: str | None = None,
        no_module_spec: bool = False,
        no_retry: bool = False,
    ) -> None:
        if target_list is None:
            target_list = []
        self._queue = list(target_list)
        self._resume = resume
        self._update = update
        self._parallel = parallel
        self._download_only = download_only
        self._include_test_contents = include_test_contents
        self._out_dir_base = out_dir
        self._no_module_spec = no_module_spec
        self._no_retry = no_retry

        use_ansible_doc = True
        if self._no_module_spec:
            use_ansible_doc = False

        read_ram = True
        write_ram = True
        if self._include_test_contents:
            read_ram = False
            write_ram = False

        self._scanner = ARIScanner(
            root_dir=config.data_dir,
            silent=True,
            use_ansible_doc=use_ansible_doc,
            persist_dependency_cache=True,
            read_ram=read_ram,
            write_ram=write_ram,
        )

    def run(self) -> None:
        num = len(self._queue)
        resume_str = f"(resume from {self._resume})" if self._resume > 0 else ""
        print(f"Start scanning {num} targets {resume_str}")

        input_list = []
        for i, target_info in enumerate(self._queue):
            if i + 1 < self._resume:
                continue
            if not isinstance(target_info, tuple):
                raise ValueError(
                    f"target list must be a list of tuple(target_type, target_name), but got a {type(target_info)}"
                )
            if len(target_info) != 2:
                raise ValueError(
                    f"target list must be a list of tuple(target_type, target_name), but got this; {target_info}"
                )

            _type, _name = target_info
            input_list.append((i, num, _type, _name))

        self.start = time.time()

        if self._parallel:
            joblib.Parallel(n_jobs=-1)(
                joblib.delayed(self.scan)(i, num, _type, _name) for (i, num, _type, _name) in input_list
            )
        else:
            for i, num, _type, _name in input_list:
                self.scan(i, num, _type, _name)

    def scan(self, i: int, num: int, type: str, name: str) -> None:
        start_val = self.start if self.start is not None else time.time()
        elapsed = round(time.time() - start_val, 2)
        start_of_this_scan = time.time()
        thread_id = threading.get_native_id()
        print(f"[{i + 1}/{num}] start {type} {name} ({elapsed} sec. elapsed) (thread: {thread_id})")
        use_src_cache = True

        if self.skip_scan(type, name):
            print(f"skip ram update of {type} {name}")
            return
        fail = False
        if self._update:
            # disable dependency cache when update mode to avoid using the old src
            use_src_cache = False
        try:
            out_dir = None
            if self._out_dir_base:
                out_dir = os.path.join(self._out_dir_base, type, name)
            out_dir_str = out_dir if out_dir else ""
            self._scanner.evaluate(
                type=type,
                name=name,
                install_dependencies=True,
                download_only=self._download_only,
                include_test_contents=self._include_test_contents,
                use_src_cache=use_src_cache,
                out_dir=out_dir_str,
            )
        except Exception:
            error = traceback.format_exc()
            self._scanner.save_error(error)
            fail = True
        self.save_ram_log(type, name, fail)

        elapsed_for_this_scan = round(time.time() - start_of_this_scan, 2)
        if elapsed_for_this_scan > 60:
            print(f"WARNING: It took {elapsed_for_this_scan} sec. to process [{i + 1}/{num}] {type} {name}")

    def save_ram_log(self, type: str, name: str, fail: bool) -> None:
        out_dir = os.path.join(self._scanner.root_dir, "log", type, name)
        path = os.path.join(out_dir, "ram_log.json")

        scan_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        new_record = {"type": type, "name": name, "succeed": not fail, "time": scan_time}

        logs = []
        if os.path.exists(path):
            with open(path) as file:
                data = file.read()
                d = json.loads(data)
                logs.extend(d)
        logs.append(new_record)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        with open(path, "w") as file:
            json.dump(logs, file)
        return

    def skip_scan(self, type: str, name: str) -> bool:
        skip = False
        path = os.path.join(self._scanner.root_dir, "log", type, name, "ram_log.json")
        if not os.path.exists(path):
            return skip
        logs = []
        with open(path) as file:
            data = file.read()
            d = json.loads(data)
            logs.extend(d)
        if logs:
            latest = logs[-1]
            if latest.get("succeed", False) or self._no_retry:
                skip = True
                return skip
        return skip
