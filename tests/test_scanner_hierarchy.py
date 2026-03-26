"""Tests for integrated engine scanner hierarchy payload (build_hierarchy_payload, node_to_dict, apply_rules)."""

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from apme_engine.daemon.primary_server import (
    _build_manifest,
    _classify_collections,
    _discover_collection_specs,
    merge_collection_specs,
)
from apme_engine.engine.opa_payload import _extract_collection_set

if TYPE_CHECKING:
    from apme_engine.engine.scanner import SingleScan


def _import_single_scan() -> type["SingleScan"] | None:
    """Import SingleScan from apme_engine.engine; return None if import fails.

    Returns:
        SingleScan class or None.
    """
    try:
        from apme_engine.engine.scanner import SingleScan

        return SingleScan
    except Exception:
        return None


@pytest.fixture  # type: ignore[untyped-decorator]
def single_scan_with_mock_contexts() -> "SingleScan":
    """SingleScan with minimal mock contexts so build_hierarchy_payload runs.

    Returns:
        SingleScan instance with mock playcall and taskcall.
    """
    SingleScan = _import_single_scan()
    if SingleScan is None:
        pytest.skip("apme_engine.engine not importable (missing deps)")
    scan = SingleScan(type="playbook", name="test.yml", root_dir="/tmp", rules_dir="")  # type: ignore[misc]
    # Mock context: root_key, sequence of nodes
    mock_spec = MagicMock()
    mock_spec.defined_in = "/path/to/play.yml"
    mock_spec.line_num_in_file = [10, 12]
    mock_spec.line_number = None
    mock_spec.name = ""
    mock_task = MagicMock()
    mock_task.type = "taskcall"
    mock_task.key = "taskcall#key1"
    mock_task.spec = mock_spec
    mock_task.name = ""
    mock_task.resolved_name = "ansible.builtin.shell"
    mock_task.resolved_action = "ansible.builtin.shell"
    mock_task.annotations = []
    mock_play = MagicMock()
    mock_play.type = "playcall"
    mock_play.key = "playcall#play1"
    mock_play.spec = mock_spec
    mock_ctx = MagicMock()
    mock_ctx.root_key = "playbook :/path/to/play.yml"
    mock_ctx.sequence = [mock_play, mock_task]
    scan.contexts = [mock_ctx]
    return scan


class TestScannerHierarchy:
    """Tests for integrated engine scanner build_hierarchy_payload and apply_rules."""

    def test_build_hierarchy_payload_structure(self, single_scan_with_mock_contexts: "SingleScan") -> None:
        """build_hierarchy_payload returns dict with scan_id, hierarchy, metadata.

        Args:
            single_scan_with_mock_contexts: Fixture providing a SingleScan with mocked contexts.

        """
        scan = single_scan_with_mock_contexts
        payload = scan.build_hierarchy_payload(scan_id="fixed-id")
        assert payload["scan_id"] == "fixed-id"
        assert "hierarchy" in payload
        hierarchy = cast(list[dict[str, object]], payload["hierarchy"])
        assert len(hierarchy) == 1
        tree = hierarchy[0]
        assert tree["root_key"] == "playbook :/path/to/play.yml"
        assert tree["root_type"] == "playbook"
        assert tree["root_path"] == "/path/to/play.yml"
        nodes = cast(list[dict[str, object]], tree["nodes"])
        assert len(nodes) == 2
        metadata = cast(dict[str, object], payload["metadata"])
        assert metadata["type"] == "playbook"
        assert metadata["name"] == "test.yml"

    def test_build_hierarchy_payload_node_serialization(self, single_scan_with_mock_contexts: "SingleScan") -> None:
        """_node_to_dict serializes playcall and taskcall with file, line, module.

        Args:
            single_scan_with_mock_contexts: Fixture providing a SingleScan with mocked contexts.

        """
        scan = single_scan_with_mock_contexts
        payload = scan.build_hierarchy_payload(scan_id="x")
        hierarchy = cast(list[dict[str, object]], payload["hierarchy"])
        tree = hierarchy[0]
        nodes = cast(list[dict[str, object]], tree["nodes"])
        play_node = nodes[0]
        assert play_node["type"] == "playcall"
        assert play_node["key"] == "playcall#play1"
        assert play_node["file"] == "/path/to/play.yml"
        assert play_node["line"] == [10, 12]
        assert "module" not in play_node
        assert "name" in play_node
        assert "options" in play_node
        task_node = nodes[1]
        assert task_node["type"] == "taskcall"
        assert task_node["module"] == "ansible.builtin.shell"
        assert task_node["annotations"] == []
        assert task_node["name"] is None
        assert task_node["options"] == {}
        assert task_node["module_options"] == {}

    def test_build_hierarchy_payload_empty_scan_id_generates_timestamp(
        self, single_scan_with_mock_contexts: "SingleScan"
    ) -> None:
        """When scan_id is empty, build_hierarchy_payload uses timestamp.

        Args:
            single_scan_with_mock_contexts: Fixture providing a SingleScan with mocked contexts.

        """
        scan = single_scan_with_mock_contexts
        payload = scan.build_hierarchy_payload()
        scan_id = str(payload["scan_id"])
        assert scan_id != ""
        assert len(scan_id) >= 14  # YYYYMMDDHHMMSS

    def test_build_hierarchy_payload_empty_contexts_returns_empty_trees(self) -> None:
        """When contexts is empty, hierarchy is empty list."""
        SingleScan = _import_single_scan()
        if SingleScan is None:
            pytest.skip("apme_engine.engine not importable")
        scan = SingleScan(type="playbook", name="test.yml", root_dir="/tmp", rules_dir="")  # type: ignore[misc]
        scan.contexts = []
        payload = scan.build_hierarchy_payload(scan_id="id")
        assert payload["hierarchy"] == []

    def test_apply_rules_sets_findings_and_hierarchy_payload(
        self, single_scan_with_mock_contexts: "SingleScan"
    ) -> None:
        """apply_rules builds hierarchy_payload and sets findings with it in report.

        Args:
            single_scan_with_mock_contexts: Fixture providing a SingleScan with mocked contexts.

        """
        scan = single_scan_with_mock_contexts
        scan.apply_rules()
        assert scan.hierarchy_payload != {}
        assert scan.findings is not None
        assert "hierarchy_payload" in scan.findings.report
        assert scan.findings.report["hierarchy_payload"] == scan.hierarchy_payload
        assert scan.result is None

    def test_node_to_dict_no_spec(self) -> None:
        """node_to_dict handles node without spec (file/line empty)."""
        from apme_engine.engine.opa_payload import node_to_dict

        node = MagicMock()
        node.type = "playcall"
        node.key = "k"
        node.spec = None
        d = node_to_dict(node)
        assert d["file"] == ""
        assert d["line"] is None
        assert d["defined_in"] == ""

    def test_build_hierarchy_payload_includes_collection_set(
        self, single_scan_with_mock_contexts: "SingleScan"
    ) -> None:
        """build_hierarchy_payload includes collection_set derived from FQCN modules.

        The fixture uses ansible.builtin.shell which should be excluded,
        so the collection_set should be empty.

        Args:
            single_scan_with_mock_contexts: Fixture providing a SingleScan with mocked contexts.
        """
        scan = single_scan_with_mock_contexts
        payload = scan.build_hierarchy_payload(scan_id="cs-test")
        assert "collection_set" in payload
        assert payload["collection_set"] == []


class TestExtractCollectionSet:
    """Tests for _extract_collection_set (FQCN-based collection discovery)."""

    @staticmethod
    def _make_tree(modules: list[tuple[str, str]]) -> list[dict[str, object]]:
        """Build a minimal trees_data list from (module, original_module) pairs.

        Args:
            modules: List of (module, original_module) tuples.

        Returns:
            Single-element list of tree dicts with taskcall nodes.
        """
        nodes: list[dict[str, object]] = []
        for mod, orig in modules:
            nodes.append({"type": "taskcall", "module": mod, "original_module": orig})
        return [{"root_key": "playbook :/test.yml", "nodes": nodes}]

    def test_extracts_fqcn_collections(self) -> None:
        """Standard FQCN modules yield their namespace.collection prefix."""
        trees = self._make_tree(
            [
                ("community.general.nmcli", "nmcli"),
                ("ansible.posix.mount", "mount"),
            ]
        )
        result = _extract_collection_set(trees)
        assert result == ["ansible.posix", "community.general"]

    def test_excludes_ansible_builtin(self) -> None:
        """ansible.builtin is always available and must be excluded."""
        trees = self._make_tree(
            [
                ("ansible.builtin.shell", "shell"),
                ("ansible.builtin.copy", "copy"),
            ]
        )
        assert _extract_collection_set(trees) == []

    def test_deduplicates(self) -> None:
        """Multiple modules from the same collection produce one entry."""
        trees = self._make_tree(
            [
                ("community.general.nmcli", "nmcli"),
                ("community.general.parted", "parted"),
                ("community.general.timezone", "timezone"),
            ]
        )
        assert _extract_collection_set(trees) == ["community.general"]

    def test_short_names_ignored(self) -> None:
        """Short module names (< 3 parts) are not treated as FQCNs."""
        trees = self._make_tree(
            [
                ("copy", ""),
                ("ansible.legacy", ""),
            ]
        )
        assert _extract_collection_set(trees) == []

    def test_path_like_values_rejected(self) -> None:
        """Taskfile paths and URLs with dots are not misidentified as FQCNs."""
        trees = self._make_tree(
            [
                ("roles/my.task.yml", ""),
                ("includes/setup.network.tasks", ""),
                ("/absolute/path.to.file", ""),
                ("http://example.com.foo", ""),
                ("has spaces.not.fqcn", ""),
            ]
        )
        assert _extract_collection_set(trees) == []

    def test_empty_trees(self) -> None:
        """Empty tree list produces empty collection set."""
        assert _extract_collection_set([]) == []

    def test_no_taskcall_nodes(self) -> None:
        """Trees with only non-taskcall nodes produce empty collection set."""
        trees: list[dict[str, object]] = [
            {"nodes": [{"type": "playcall", "module": "community.general.nmcli"}]},
        ]
        assert _extract_collection_set(trees) == []

    def test_uses_original_module_field(self) -> None:
        """Collections are extracted from original_module when module differs."""
        trees = self._make_tree(
            [
                ("ansible.builtin.shell", "custom.collection.my_shell"),
            ]
        )
        result = _extract_collection_set(trees)
        assert "custom.collection" in result

    def test_none_module_values_handled(self) -> None:
        """None values for module fields don't cause errors."""
        trees: list[dict[str, object]] = [
            {"nodes": [{"type": "taskcall", "module": None, "original_module": None}]},
        ]
        assert _extract_collection_set(trees) == []

    def test_sorted_output(self) -> None:
        """Output is deterministically sorted."""
        trees = self._make_tree(
            [
                ("z_vendor.z_coll.mod", ""),
                ("a_vendor.a_coll.mod", ""),
                ("m_vendor.m_coll.mod", ""),
            ]
        )
        result = _extract_collection_set(trees)
        assert result == ["a_vendor.a_coll", "m_vendor.m_coll", "z_vendor.z_coll"]

    def test_multiple_trees(self) -> None:
        """Collections from multiple trees are aggregated and deduplicated."""
        tree1: dict[str, object] = {
            "nodes": [{"type": "taskcall", "module": "community.general.nmcli", "original_module": ""}],
        }
        tree2: dict[str, object] = {
            "nodes": [{"type": "taskcall", "module": "ansible.posix.mount", "original_module": ""}],
        }
        tree3: dict[str, object] = {
            "nodes": [{"type": "taskcall", "module": "community.general.parted", "original_module": ""}],
        }
        result = _extract_collection_set([tree1, tree2, tree3])
        assert result == ["ansible.posix", "community.general"]


class TestCollectionSpecMerge:
    """Tests for merge_collection_specs (collection precedence logic).

    Exercises the merge semantics: explicit specs (from the request or
    requirements.yml) take precedence over bare FQCN-derived specs.
    Calls the real production helper directly.
    """

    def test_requirements_yml_wins_over_hierarchy(self) -> None:
        """Versioned spec from requirements.yml supersedes bare hierarchy spec."""
        result = merge_collection_specs(
            request_specs=[],
            discovered_specs=["community.general:>=5.0.0"],
            hierarchy_collections=["community.general"],
        )
        assert result == ["community.general:>=5.0.0"]

    def test_request_specs_win_over_both(self) -> None:
        """Specs from the original request take highest precedence."""
        result = merge_collection_specs(
            request_specs=["community.general:==4.0.0"],
            discovered_specs=["community.general:>=5.0.0"],
            hierarchy_collections=["community.general"],
        )
        assert result == ["community.general:==4.0.0"]

    def test_hierarchy_supplements_missing(self) -> None:
        """Hierarchy-derived collections fill gaps not covered by requirements.yml."""
        result = merge_collection_specs(
            request_specs=[],
            discovered_specs=["community.general:>=5.0.0"],
            hierarchy_collections=["ansible.posix", "community.crypto"],
        )
        assert "community.general:>=5.0.0" in result
        assert "ansible.posix" in result
        assert "community.crypto" in result
        assert len(result) == 3

    def test_all_empty(self) -> None:
        """No specs from any source produces empty list."""
        assert merge_collection_specs([], [], []) == []

    def test_deduplication_across_sources(self) -> None:
        """Same collection in all three sources appears only once."""
        result = merge_collection_specs(
            request_specs=["community.general:==4.0.0"],
            discovered_specs=["community.general:>=5.0.0"],
            hierarchy_collections=["community.general"],
        )
        bare_names = [s.split(":")[0] for s in result]
        assert bare_names.count("community.general") == 1

    def test_hierarchy_only(self) -> None:
        """When no requirements.yml exists, hierarchy provides all specs as bare."""
        result = merge_collection_specs(
            request_specs=[],
            discovered_specs=[],
            hierarchy_collections=["community.general", "ansible.posix"],
        )
        assert sorted(result) == ["ansible.posix", "community.general"]


class TestDiscoverCollectionSpecs:
    """Tests for _discover_collection_specs requirements file discovery."""

    def _file(self, path: str, content: str) -> MagicMock:
        """Build a fake File proto.

        Args:
            path: File path.
            content: YAML content string.

        Returns:
            MagicMock with path and content attributes.
        """
        f = MagicMock()
        f.path = path
        f.content = content.encode()
        return f

    def test_discovers_requirements_yml(self) -> None:
        """Finds specs and paths from requirements.yml."""
        content = "collections:\n  - community.general\n  - name: ansible.posix\n    version: '2.0.0'\n"
        files = [self._file("requirements.yml", content)]
        specs, paths = _discover_collection_specs(files)
        assert "community.general" in specs
        assert "ansible.posix:2.0.0" in specs
        assert paths == ["requirements.yml"]

    def test_discovers_nested_requirements(self) -> None:
        """Finds specs from collections/requirements.yml."""
        content = "collections:\n  - community.crypto\n"
        files = [self._file("collections/requirements.yml", content)]
        specs, paths = _discover_collection_specs(files)
        assert specs == ["community.crypto"]
        assert paths == ["collections/requirements.yml"]

    def test_returns_empty_for_no_match(self) -> None:
        """No requirements files returns empty."""
        files = [self._file("playbook.yml", "- hosts: all\n")]
        specs, paths = _discover_collection_specs(files)
        assert specs == []
        assert paths == []

    def test_paths_reported_even_without_collections_key(self) -> None:
        """File path is reported even if YAML has no collections key."""
        files = [self._file("requirements.yml", "roles:\n  - some.role\n")]
        specs, paths = _discover_collection_specs(files)
        assert specs == []
        assert paths == ["requirements.yml"]


class TestBuildManifest:
    """Tests for _build_manifest ProjectManifest construction."""

    def test_builds_from_session_state(self) -> None:
        """Manifest is built from session manifest fields including packages."""
        from apme_engine.daemon.session import SessionState

        session = SessionState(session_id="s1")
        session.ansible_core_version = "2.16.3"
        session.installed_collections = [
            ("community.general", "8.0.0", "specified"),
            ("ansible.posix", "1.5.4", "learned"),
        ]
        session.installed_packages = [("ansible-core", "2.16.3"), ("jinja2", "3.1.2")]
        session.dependency_tree = "ansible-core v2.16.3\n├── jinja2 v3.1.2"
        session.requirements_files = ["requirements.yml"]

        manifest = _build_manifest(session)
        assert manifest.ansible_core_version == "2.16.3"
        assert len(manifest.collections) == 2
        assert manifest.collections[0].fqcn == "community.general"
        assert manifest.collections[0].version == "8.0.0"
        assert manifest.collections[0].source == "specified"
        assert manifest.collections[1].fqcn == "ansible.posix"
        assert manifest.collections[1].version == "1.5.4"
        assert manifest.collections[1].source == "learned"
        assert len(manifest.python_packages) == 2
        assert manifest.python_packages[0].name == "ansible-core"
        assert manifest.python_packages[0].version == "2.16.3"
        assert manifest.python_packages[1].name == "jinja2"
        assert manifest.python_packages[1].version == "3.1.2"
        assert list(manifest.requirements_files) == ["requirements.yml"]
        assert "ansible-core v2.16.3" in manifest.dependency_tree

    def test_empty_session_produces_empty_manifest(self) -> None:
        """Session with no manifest data produces empty (but valid) manifest."""
        from apme_engine.daemon.session import SessionState

        session = SessionState(session_id="s2")
        manifest = _build_manifest(session)
        assert manifest.ansible_core_version == ""
        assert len(manifest.collections) == 0
        assert len(manifest.python_packages) == 0
        assert len(manifest.requirements_files) == 0
        assert manifest.dependency_tree == ""


class TestClassifyCollections:
    """Tests for _classify_collections source classification."""

    def test_specified_from_requirements(self) -> None:
        """Collections in specified_fqcns are classified as 'specified'."""
        installed = [("community.general", "8.0.0"), ("ansible.posix", "1.5.4")]
        result = _classify_collections(installed, {"community.general"}, set())
        assert result[0] == ("community.general", "8.0.0", "specified")

    def test_learned_from_hierarchy(self) -> None:
        """Collections in learned_fqcns are classified as 'learned'."""
        installed = [("ansible.posix", "1.5.4")]
        result = _classify_collections(installed, set(), {"ansible.posix"})
        assert result[0] == ("ansible.posix", "1.5.4", "learned")

    def test_dependency_for_unknown(self) -> None:
        """Collections in neither set are classified as 'dependency'."""
        installed = [("ansible.utils", "3.0.0")]
        result = _classify_collections(installed, set(), set())
        assert result[0] == ("ansible.utils", "3.0.0", "dependency")

    def test_specified_takes_priority_over_learned(self) -> None:
        """When in both sets, specified wins."""
        installed = [("community.general", "8.0.0")]
        result = _classify_collections(installed, {"community.general"}, {"community.general"})
        assert result[0][2] == "specified"

    def test_empty_installed(self) -> None:
        """Empty installed list produces empty result."""
        assert _classify_collections([], {"a.b"}, {"c.d"}) == []
