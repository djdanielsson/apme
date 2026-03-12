from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import jsonpickle

from .utils import (
    lock_file,
    remove_lock_file,
    unlock_file,
)


@dataclass
class Findings:
    metadata: dict[str, Any] = field(default_factory=dict)
    dependencies: list[Any] = field(default_factory=list)

    root_definitions: dict[str, Any] = field(default_factory=dict)
    ext_definitions: dict[str, Any] = field(default_factory=dict)
    extra_requirements: list[Any] = field(default_factory=list)
    resolve_failures: dict[str, Any] = field(default_factory=dict)

    prm: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)

    summary_txt: str = ""
    scan_time: str = ""

    def simple(self) -> dict[str, Any]:
        d = self.report.copy()
        d["metadata"] = self.metadata
        d["dependencies"] = self.dependencies
        return d

    def dump(self, fpath: str = "") -> str:
        f = deepcopy(self)
        # omit report and summary_txt when the findings are saved
        # to reduce unnecessary file write
        f.report = {}
        f.summary_txt = ""
        json_str = jsonpickle.encode(f, make_refs=False)
        if fpath:
            lock = lock_file(fpath)
            try:
                with open(fpath, "w") as file:
                    file.write(json_str)
            finally:
                unlock_file(lock)
                remove_lock_file(lock)
        return str(json_str)

    def save_rule_result(self, fpath: str = "") -> str:
        json_str: str = jsonpickle.encode(self.report.get("ari_result", {}), make_refs=False, unpicklable=False)
        if fpath:
            rule_result_dir = os.path.dirname(fpath)
            if not os.path.exists(rule_result_dir):
                os.makedirs(rule_result_dir, exist_ok=True)
            with open(fpath, "w") as file:
                file.write(json_str)
        return json_str

    @staticmethod
    def load(fpath: str = "", json_str: str = "") -> Findings:
        if fpath:
            with open(fpath) as file:
                json_str = file.read()
        findings: Findings = jsonpickle.decode(json_str)
        return findings
