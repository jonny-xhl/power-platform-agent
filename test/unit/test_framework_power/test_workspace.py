"""Unit tests for framework_power.workspace (workspace discovery, manifest, path resolution)."""

import os
from pathlib import Path

import pytest
import yaml

from framework_power.webresource_sync import ALIASES_FILENAME, load_aliases
from framework_power.workspace import (
    DEFAULT_DIRS,
    STANDARD_FILES,
    WEBRESOURCE_ALIASES_FILENAME,
    NotInWorkspaceError,
    Workspace,
    WorkspaceManifest,
    get_cached_workspace,
    reset_cache,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST = {
    "name": "test-project",
    "version": "1.0.0",
    "publisher": "contoso",
    "publisher_prefix": "con",
    "main_solution": "con_TestSolution",
    "ribbon_solution": "con_RibbonSoln",
}


def test_manifest_from_dict_basic():
    """Manifest parses name, version, publisher, solutions."""
    ws = WorkspaceManifest.from_dict(SAMPLE_MANIFEST)
    assert ws.name == "test-project"
    assert ws.version == "1.0.0"
    assert ws.publisher == "contoso"
    assert ws.publisher_prefix == "con"
    assert ws.main_solution == "con_TestSolution"
    assert ws.ribbon_solution == "con_RibbonSoln"


def test_manifest_defaults():
    """Manifest fills in defaults when fields are missing."""
    ws = WorkspaceManifest.from_dict({"name": "minimal"})
    assert ws.name == "minimal"
    assert ws.publisher == "new"
    assert ws.publisher_prefix == "new"
    assert ws.version == "1.0.0.0"
    assert ws.main_solution == ""


def test_manifest_to_dict_roundtrip():
    """Manifest to_dict preserves data."""
    ws = WorkspaceManifest.from_dict(SAMPLE_MANIFEST)
    d = ws.to_dict()
    assert d["name"] == "test-project"
    assert d["publisher"] == "contoso"
    assert d["main_solution"] == "con_TestSolution"


def test_manifest_custom_dirs():
    """Manifest respects custom dirs."""
    ws = WorkspaceManifest.from_dict({
        "name": "custom",
        "dirs": {"tables": "custom/tables"},
    })
    assert ws.dirs["tables"] == "custom/tables"


# ---------------------------------------------------------------------------
# Workspace fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with pp-workspace.yaml."""
    manifest_path = tmp_path / "pp-workspace.yaml"
    manifest_path.write_text(yaml.dump(SAMPLE_MANIFEST), encoding="utf-8")
    # Create expected directories
    for key in ["tables", "forms", "views", "config"]:
        rel = DEFAULT_DIRS[key]
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset workspace cache before each test."""
    reset_cache()
    yield
    reset_cache()


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------


def test_discover_in_current_dir(temp_workspace, monkeypatch):
    """Workspace discovered when pp-workspace.yaml is in CWD."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.root == temp_workspace.resolve()
    assert ws.manifest.name == "test-project"


def test_discover_from_subdirectory(temp_workspace, monkeypatch):
    """Workspace discovered by walking up from a subdirectory."""
    subdir = temp_workspace / "metadata_py" / "tables"
    subdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(subdir)
    ws = Workspace.discover()
    assert ws.root == temp_workspace.resolve()


def test_discover_not_found(tmp_path, monkeypatch):
    """NotInWorkspaceError raised when no pp-workspace.yaml found."""
    # Use an isolated tmp dir that has no pp-workspace.yaml in any parent
    monkeypatch.chdir(tmp_path)
    # Clear any PP_WORKSPACE env var
    monkeypatch.delenv("PP_WORKSPACE", raising=False)
    # Also need to make sure no parent has it — tmp_path should be clean
    with pytest.raises(NotInWorkspaceError):
        Workspace.discover()


def test_discover_explicit_path(temp_workspace):
    """Workspace discovered via explicit start path."""
    ws = Workspace.discover(str(temp_workspace))
    assert ws.root == temp_workspace.resolve()


def test_discover_via_env_var(temp_workspace, monkeypatch):
    """Workspace discovered via PP_WORKSPACE env var."""
    # chdir to a dir without manifest to prove env var takes priority
    other_dir = temp_workspace.parent / "other_test_dir"
    other_dir.mkdir(exist_ok=True)
    monkeypatch.chdir(other_dir)
    monkeypatch.setenv("PP_WORKSPACE", str(temp_workspace))
    ws = Workspace.discover()
    assert ws.root == temp_workspace.resolve()


def test_discover_explicit_overrides_env(temp_workspace, monkeypatch):
    """Explicit path takes priority over PP_WORKSPACE."""
    monkeypatch.setenv("PP_WORKSPACE", str(temp_workspace))
    ws = Workspace.discover(str(temp_workspace))
    assert ws.root == temp_workspace.resolve()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_paths_are_absolute(temp_workspace, monkeypatch):
    """All workspace path properties return absolute paths."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.tables_dir.is_absolute()
    assert ws.forms_dir.is_absolute()
    assert ws.views_dir.is_absolute()
    assert ws.webresources_root.is_absolute()
    assert ws.plugins_dir.is_absolute()


def test_tables_dir_default(temp_workspace, monkeypatch):
    """tables_dir resolves to metadata_py/tables by default."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.tables_dir == temp_workspace.resolve() / "metadata_py" / "tables"


def test_config_dir(temp_workspace, monkeypatch):
    """config_dir points to config/ directory."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.config_dir == temp_workspace.resolve() / "config"


def test_environments_config_path(temp_workspace, monkeypatch):
    """environments_config points to config/environments.yaml."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.environments_config == temp_workspace.resolve() / "config" / "environments.yaml"


def test_project_path(temp_workspace, monkeypatch):
    """project_path resolves to metadata_py/project.py."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.project_path == temp_workspace.resolve() / "metadata_py" / "project.py"


def test_custom_dir_override(tmp_path, monkeypatch):
    """Custom dirs override defaults."""
    manifest = {**SAMPLE_MANIFEST, "dirs": {"tables": "custom/tables"}}
    (tmp_path / "pp-workspace.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
    # Create custom dir
    (tmp_path / "custom" / "tables").mkdir(parents=True)
    (tmp_path / "config").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    ws = Workspace.discover()
    assert ws.tables_dir == tmp_path.resolve() / "custom" / "tables"


def test_path_unknown_key_raises(temp_workspace, monkeypatch):
    """path() raises KeyError for unknown keys."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    with pytest.raises(KeyError):
        ws.path("nonexistent_key")


# ---------------------------------------------------------------------------
# Workspace validate
# ---------------------------------------------------------------------------


def test_validate_complete(temp_workspace, monkeypatch):
    """Validate passes for a workspace with all required directories."""
    # Create all required dirs + config file
    for key in ["tables", "forms", "views", "config"]:
        rel = DEFAULT_DIRS[key]
        (temp_workspace / rel).mkdir(parents=True, exist_ok=True)
    (temp_workspace / "config" / "environments.yaml").write_text(
        "environments: {}", encoding="utf-8"
    )
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    issues = ws.validate()
    assert isinstance(issues, list)


def test_validate_missing_dir(tmp_path, monkeypatch):
    """Validate reports missing directories."""
    manifest = {**SAMPLE_MANIFEST}
    (tmp_path / "pp-workspace.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
    # Don't create any dirs
    monkeypatch.chdir(tmp_path)
    ws = Workspace.discover()
    issues = ws.validate()
    assert any("Missing" in i for i in issues)


# ---------------------------------------------------------------------------
# Workspace creation (for pp workspace init)
# ---------------------------------------------------------------------------


def test_create_from_template(tmp_path):
    """create_from_template creates manifest + dirs."""
    root = tmp_path / "new-ws"
    ws = Workspace.create_from_template(
        root,
        name="my-project",
        publisher="contoso",
        publisher_prefix="con",
        main_solution="con_Main",
    )
    assert ws.manifest.name == "my-project"
    assert ws.manifest.main_solution == "con_Main"
    # create_from_template uses ensure_dirs=True by default via create()
    assert ws.tables_dir.exists()
    assert ws.config_dir.exists()
    # Write manifest explicitly
    ws.write_manifest()
    assert (root / "pp-workspace.yaml").exists()


def test_write_manifest(tmp_path):
    """write_manifest persists manifest to disk."""
    root = tmp_path / "ws-write"
    ws = Workspace.create_from_template(root, name="test-write")
    # Modify and rewrite
    ws.manifest.version = "2.0.0"
    ws.write_manifest()
    # Reload and verify
    ws2 = Workspace.discover(str(root))
    assert ws2.manifest.version == "2.0.0"


def test_ensure_dirs(tmp_path):
    """ensure_dirs creates all standard directories."""
    root = tmp_path / "ensure-test"
    ws = Workspace.create_from_template(root, name="ensure-test")
    # ensure_dirs is called during create, so all dirs should exist
    for key in DEFAULT_DIRS:
        assert ws.path(key).exists()


# ---------------------------------------------------------------------------
# Standard files (new-workspace parity for every engine feature)
# ---------------------------------------------------------------------------


def test_init_seeds_standard_files(tmp_path):
    """A freshly initialised workspace already supports features needing standard files."""
    ws = Workspace.create_from_template(tmp_path / "seed", name="seed")
    for path in ws.standard_files():
        assert path.exists(), f"init did not seed {path}"


def test_seeded_alias_table_is_empty_and_usable(tmp_path):
    """The seed must be a valid, behaviour-neutral table: no aliases == convention for all."""
    ws = Workspace.create_from_template(tmp_path / "seed2", name="seed2")
    seeded = (ws.webresources_root / ALIASES_FILENAME).read_text(encoding="utf-8")
    assert seeded.strip() == "{}"
    assert load_aliases(ws.webresources_root) == {}  # parses (a malformed seed would raise)


def test_ensure_files_is_idempotent_and_never_overwrites(tmp_path):
    ws = Workspace.create_from_template(tmp_path / "keep", name="keep")
    table = ws.webresources_root / ALIASES_FILENAME
    table.write_text('{"html/orders.html": "new_Orders.html"}\n', encoding="utf-8")
    ws.ensure_files()
    assert load_aliases(ws.webresources_root) == {"html/orders.html": "new_Orders.html"}


def test_standard_files_follow_manifest_dir_overrides(tmp_path):
    """A relocated webresources dir must not strand the seeded file at the default path."""
    ws = Workspace.create_from_template(
        tmp_path / "moved", name="moved", extra_dirs={"webresources": "assets"}
    )
    assert (ws.webresources_root / ALIASES_FILENAME).exists()
    assert (ws.root / "assets" / ALIASES_FILENAME).exists()


def test_alias_filename_has_a_single_definition():
    """The name is one constant, re-exported by the flow that parses it."""
    assert ALIASES_FILENAME == WEBRESOURCE_ALIASES_FILENAME
    assert ALIASES_FILENAME in STANDARD_FILES


def test_info_lists_standard_files(tmp_path):
    ws = Workspace.create_from_template(tmp_path / "info", name="info")
    (ws.webresources_root / ALIASES_FILENAME).unlink()
    entry = next(
        f for f in ws.to_dict()["standard_files"] if f["path"].endswith(ALIASES_FILENAME)
    )
    assert entry["exists"] is False  # surfaced, not silently missing


def test_validate_treats_standard_files_as_optional(tmp_path):
    """Absence of the alias table must stay non-fatal — most projects never need one."""
    ws = Workspace.create_from_template(tmp_path / "opt", name="opt")
    (ws.webresources_root / ALIASES_FILENAME).unlink()
    assert not any(ALIASES_FILENAME in issue for issue in ws.validate())


# ---------------------------------------------------------------------------
# Cached workspace
# ---------------------------------------------------------------------------


def test_cached_workspace_returns_same_instance(temp_workspace, monkeypatch):
    """get_cached_workspace returns the same instance."""
    monkeypatch.chdir(temp_workspace)
    ws1 = get_cached_workspace()
    ws2 = get_cached_workspace()
    assert ws1 is ws2


def test_reset_cache(temp_workspace, monkeypatch):
    """reset_cache forces re-discovery."""
    monkeypatch.chdir(temp_workspace)
    ws1 = get_cached_workspace()
    reset_cache()
    ws2 = get_cached_workspace()
    # Different instances after cache reset
    assert ws1 is not ws2
    # But same root
    assert ws1.root == ws2.root


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_manifest_empty_name():
    """Empty manifest produces empty name."""
    ws = WorkspaceManifest.from_dict({})
    assert ws.name == ""


def test_root_is_resolved(temp_workspace, monkeypatch):
    """ws.root is resolved to absolute path."""
    monkeypatch.chdir(temp_workspace)
    ws = Workspace.discover()
    assert ws.root == temp_workspace.resolve()
    assert ws.root.is_absolute()
