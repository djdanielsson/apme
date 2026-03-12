from __future__ import annotations

import os
from typing import Any

key_delimiter = ":"
object_delimiter = "#"


class Key:
    def __init__(self, key_str: str) -> None:
        self.key = key_str

    def detect_type(self) -> str:
        return self.key.split(" ")[0]

    # convert key to tree root name
    def to_name(self) -> str | None:
        _type = self.detect_type()
        if _type == "playbook":
            return os.path.basename(self.key.split(key_delimiter)[-1])
        elif _type == "role":
            return self.key.split(key_delimiter)[-1]
        return None


def make_global_key_prefix(collection: str, role: str) -> str:
    key_prefix = ""
    if collection != "":
        key_prefix = f"collection{key_delimiter}{collection}{object_delimiter}"
    elif role != "":
        key_prefix = f"role{key_delimiter}{role}{object_delimiter}"
    return key_prefix


def detect_type(key: str = "") -> str:
    return key.split(" ")[0]


def set_play_key(obj: Any, parent_key: str = "", parent_local_key: str = "") -> None:
    type_str = obj.type
    index_info = f"[{obj.index}]"
    _parent_key = parent_key.split(" ")[-1]
    _parent_local_key = parent_local_key.split(" ")[-1]
    global_key = f"{type_str} {_parent_key}{object_delimiter}{type_str}{key_delimiter}{index_info}"
    local_key = f"{type_str} {_parent_local_key}{object_delimiter}{type_str}{key_delimiter}{index_info}"
    obj.key = global_key
    obj.local_key = local_key


def set_role_key(obj: Any) -> None:
    global_key_prefix = make_global_key_prefix(obj.collection, "")
    global_key = f"{obj.type} {global_key_prefix}{obj.type}{key_delimiter}{obj.fqcn}"
    local_key = f"{obj.type} {obj.type}{key_delimiter}{obj.defined_in}"
    obj.key = global_key
    obj.local_key = local_key


def set_module_key(obj: Any) -> None:
    global_key_prefix = make_global_key_prefix(obj.collection, obj.role)
    global_key = f"{obj.type} {global_key_prefix}{obj.type}{key_delimiter}{obj.fqcn}"
    local_key = f"{obj.type} {obj.type}{key_delimiter}{obj.defined_in}"
    obj.key = global_key
    obj.local_key = local_key


def set_collection_key(obj: Any) -> None:
    global_key = f"{obj.type} {obj.type}{key_delimiter}{obj.name}"
    local_key = global_key
    obj.key = global_key
    obj.local_key = local_key


def get_obj_type(key: str) -> str | None:
    idx0 = key.find(" ")
    obj_type = key[:idx0]
    if obj_type in [
        "module",
        "play",
        "playbook",
        "role",
        "collection",
        "task",
        "taskfile",
        "repository",
    ]:
        return obj_type
    else:
        return None


def get_obj_info_by_key(key: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    info["key"] = key
    skip = False

    idx0 = key.find(" ")
    obj_type = key[:idx0]
    info["type"] = obj_type
    skip = idx0 < 0
    if not skip:
        s1 = key[idx0 + 1 :]
        if obj_type == "task" or obj_type == "play":
            idx1 = s1.find(object_delimiter)
            parent_key = s1[:idx1]
            info["parent_key"] = parent_key
            sidx1 = parent_key.find(":")
            parent_type = parent_key[:sidx1]
            info["parent_type"] = parent_type
            parent_name = parent_key[sidx1 + 1 :]
            info["parent_name"] = parent_name
            skip = skip or idx1 < 0
            if not skip:
                s2 = s1[idx1 + 1 :]
                idx2 = s2.find(key_delimiter)
                obj_type = s2[:idx2]
                info["obj_type"] = obj_type
                skip = skip or idx2 < 0
            if not skip:
                obj_key = s2[idx2 + 1 :]
                info["obj_key"] = obj_key
        elif obj_type == "taskfile" or obj_type == "playbook":
            idx1 = s1.find(key_delimiter)
            skip = skip or idx1 < 0
            if not skip:
                parent_type = s1[:idx1]
                info["parent_type"] = parent_type
                s2 = s1[idx1 + 1 :]
                idx2 = s2.find(object_delimiter)
                skip = skip or idx2 < 0
            if not skip:
                parent_name = s2[:idx2]
                info["parent_name"] = parent_name
                s3 = s2[idx2 + 1 :]
                idx3 = s3.find(key_delimiter)
                skip = skip or idx3 < 0
            if not skip:
                defined_in = s3[idx3 + 1 :]
                info["defined_in"] = defined_in
        elif obj_type == "role" or obj_type == "module":
            idx1 = s1.find(key_delimiter)
            parent_type = s1[:idx1]
            info["parent_type"] = parent_type
            skip = skip or idx1 < 0
            if not skip:
                s2 = s1[idx1 + 1 :]
                idx2 = s2.find(object_delimiter)
                parent_name = s2[:idx2]
                info["parent_name"] = parent_name
                skip = skip or idx2 < 0
            if not skip:
                s3 = s2[idx2 + 1 :]
                idx3 = s3.find(key_delimiter)
                skip = skip or idx3 < 0
            if not skip:
                fqcn = s3[idx3 + 1 :]
                info["fqcn"] = fqcn
        elif obj_type == "collection" or obj_type == "repository":
            idx1 = s1.find(key_delimiter)
            skip = skip or idx1 < 0
            if not skip:
                name = s1[idx1 + 1 :]
                info["name"] = name
        else:
            pass

    return info


def set_task_key(obj: Any, parent_key: str = "", parent_local_key: str = "") -> None:
    index_info = f"[{obj.index}]"
    _parent_key = parent_key.split(" ")[-1]
    _parent_local_key = parent_local_key.split(" ")[-1]
    global_key = f"{obj.type} {_parent_key}{object_delimiter}{obj.type}{key_delimiter}{index_info}"
    local_key = f"{obj.type} {_parent_local_key}{object_delimiter}{obj.type}{key_delimiter}{index_info}"
    obj.key = global_key
    obj.local_key = local_key


def set_taskfile_key(obj: Any) -> None:
    global_key_prefix = make_global_key_prefix(obj.collection, obj.role)
    global_key = f"{obj.type} {global_key_prefix}{obj.type}{key_delimiter}{obj.defined_in}"
    local_key = f"{obj.type} {obj.type}{key_delimiter}{obj.defined_in}"
    obj.key = global_key
    obj.local_key = local_key


def set_playbook_key(obj: Any) -> None:
    global_key_prefix = make_global_key_prefix(obj.collection, obj.role)
    global_key = f"{obj.type} {global_key_prefix}{obj.type}{key_delimiter}{obj.defined_in}"
    local_key = f"{obj.type} {obj.type}{key_delimiter}{obj.defined_in}"
    obj.key = global_key
    obj.local_key = local_key


def set_repository_key(obj: Any) -> None:
    global_key = f"{obj.type} {obj.type}{key_delimiter}{obj.name}"
    local_key = global_key
    obj.key = global_key
    obj.local_key = local_key


def set_call_object_key(cls_name: str, spec_key: str, caller_key: str) -> str:
    parts = spec_key.split(" ", 1)
    caller_only = caller_key.split(" FROM ")[0]
    return f"{cls_name} {parts[1]} FROM {caller_only}"


def make_imported_taskfile_key(caller_key: str, path: str) -> str:
    caller_key_payload = caller_key.split(" ")[-1]
    parts = caller_key_payload.split(object_delimiter)
    parent = ""
    if parts[0].startswith(("collection", "role")):
        parent = parts[0] + object_delimiter
    normed_path = os.path.normpath(path)
    key = f"taskfile {parent}taskfile{key_delimiter}{normed_path}"
    return key


def set_file_key(obj: Any) -> None:
    global_key_prefix = make_global_key_prefix(obj.collection, obj.role)
    global_key = f"{obj.type} {global_key_prefix}{obj.type}{key_delimiter}{obj.defined_in}"
    local_key = f"{obj.type} {obj.type}{key_delimiter}{obj.defined_in}"
    obj.key = global_key
    obj.local_key = local_key
