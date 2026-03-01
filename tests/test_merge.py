"""Tests for merge.py"""

import json
import shutil
from pathlib import Path

import pytest

from merge import deep_merge_json, merge_directories, merge_text


# ---------------------------------------------------------------------------
# deep_merge_json
# ---------------------------------------------------------------------------


class TestDeepMergeJson:
    def test_common_only_keys_preserved(self):
        result = deep_merge_json({"a": 1}, {})
        assert result == {"a": 1}

    def test_os_only_keys_added(self):
        result = deep_merge_json({}, {"b": 2})
        assert result == {"b": 2}

    def test_scalar_conflict_os_wins(self):
        result = deep_merge_json({"x": "common"}, {"x": "os"})
        assert result["x"] == "os"

    def test_array_conflict_os_replaces(self):
        result = deep_merge_json({"arr": [1, 2, 3]}, {"arr": [4, 5]})
        assert result["arr"] == [4, 5]

    def test_nested_dict_recursively_merged(self):
        common = {"hooks": {"PreToolUse": ["a"]}}
        os_specific = {"hooks": {"PostToolUse": ["b"]}}
        result = deep_merge_json(common, os_specific)
        assert result == {"hooks": {"PreToolUse": ["a"], "PostToolUse": ["b"]}}

    def test_nested_dict_os_scalar_wins(self):
        common = {"settings": {"theme": "light", "font": "mono"}}
        os_specific = {"settings": {"theme": "dark"}}
        result = deep_merge_json(common, os_specific)
        assert result == {"settings": {"theme": "dark", "font": "mono"}}

    def test_deeply_nested_merge(self):
        common = {"a": {"b": {"c": 1, "d": 2}}}
        os_specific = {"a": {"b": {"c": 99, "e": 3}}}
        result = deep_merge_json(common, os_specific)
        assert result == {"a": {"b": {"c": 99, "d": 2, "e": 3}}}

    def test_original_dicts_not_mutated(self):
        common = {"a": 1}
        os_specific = {"a": 2, "b": 3}
        deep_merge_json(common, os_specific)
        assert common == {"a": 1}
        assert os_specific == {"a": 2, "b": 3}


# ---------------------------------------------------------------------------
# merge_text
# ---------------------------------------------------------------------------


class TestMergeText:
    def test_concatenates_with_newline(self):
        result = merge_text("common content\n", "os content\n")
        assert result == "common content\nos content\n"

    def test_adds_newline_if_missing(self):
        result = merge_text("common content", "os content")
        assert result == "common content\nos content"

    def test_empty_common(self):
        result = merge_text("", "os content")
        assert result == "os content"

    def test_empty_os(self):
        result = merge_text("common content\n", "")
        assert result == "common content\n"


# ---------------------------------------------------------------------------
# merge_directories (integration-style with tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path):
    """Create a minimal fake repo layout."""
    common = tmp_path / "common"
    common.mkdir()
    os_dir = tmp_path / "windows"
    os_dir.mkdir()
    dest = tmp_path / "dest"
    return tmp_path, common, os_dir, dest


class TestMergeDirectories:
    def test_common_only_file_copied(self, repo):
        _, common, os_dir, dest = repo
        (common / "settings.json").write_text('{"a": 1}', encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "settings.json").read_text(encoding="utf-8"))
        assert result == {"a": 1}

    def test_os_only_file_copied(self, repo):
        _, common, os_dir, dest = repo
        (os_dir / "extra.json").write_text('{"b": 2}', encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "extra.json").read_text(encoding="utf-8"))
        assert result == {"b": 2}

    def test_json_files_deep_merged(self, repo):
        _, common, os_dir, dest = repo
        (common / "settings.json").write_text(
            json.dumps({"autoUpdatesChannel": "latest", "enabledPlugins": {"plugin-a": True}}),
            encoding="utf-8",
        )
        (os_dir / "settings.json").write_text(
            json.dumps({"hooks": {"Notification": [{"matcher": "", "hooks": []}]}}),
            encoding="utf-8",
        )

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "settings.json").read_text(encoding="utf-8"))
        assert result["autoUpdatesChannel"] == "latest"
        assert result["enabledPlugins"] == {"plugin-a": True}
        assert "Notification" in result["hooks"]

    def test_json_os_scalar_wins(self, repo):
        _, common, os_dir, dest = repo
        (common / "settings.json").write_text('{"channel": "latest"}', encoding="utf-8")
        (os_dir / "settings.json").write_text('{"channel": "beta"}', encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "settings.json").read_text(encoding="utf-8"))
        assert result["channel"] == "beta"

    def test_json_os_array_replaces(self, repo):
        _, common, os_dir, dest = repo
        (common / "settings.json").write_text('{"items": [1, 2, 3]}', encoding="utf-8")
        (os_dir / "settings.json").write_text('{"items": [4, 5]}', encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "settings.json").read_text(encoding="utf-8"))
        assert result["items"] == [4, 5]

    def test_markdown_files_concatenated(self, repo):
        _, common, os_dir, dest = repo
        (common / "CLAUDE.md").write_text("# Common rules\n- rule 1\n", encoding="utf-8")
        (os_dir / "CLAUDE.md").write_text("# Windows rules\n- rule 2\n", encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = (dest / "CLAUDE.md").read_text(encoding="utf-8")
        assert result == "# Common rules\n- rule 1\n# Windows rules\n- rule 2\n"

    def test_unknown_type_os_wins(self, repo):
        _, common, os_dir, dest = repo
        (common / "script.sh").write_text("#!/bin/bash\necho common", encoding="utf-8")
        (os_dir / "script.sh").write_text("#!/bin/bash\necho windows", encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = (dest / "script.sh").read_text(encoding="utf-8")
        assert "windows" in result
        assert "common" not in result

    def test_no_os_dir_only_common_copied(self, repo):
        _, common, _, dest = repo
        (common / "settings.json").write_text('{"a": 1}', encoding="utf-8")

        merge_directories(common, None, dest)

        result = json.loads((dest / "settings.json").read_text(encoding="utf-8"))
        assert result == {"a": 1}

    def test_nested_subdirectory_files_handled(self, repo):
        _, common, os_dir, dest = repo
        subdir = common / "subdir"
        subdir.mkdir()
        (subdir / "config.json").write_text('{"key": "common"}', encoding="utf-8")
        os_subdir = os_dir / "subdir"
        os_subdir.mkdir()
        (os_subdir / "config.json").write_text('{"extra": "os"}', encoding="utf-8")

        merge_directories(common, os_dir, dest)

        result = json.loads((dest / "subdir" / "config.json").read_text(encoding="utf-8"))
        assert result == {"key": "common", "extra": "os"}

    def test_dest_created_if_missing(self, repo):
        _, common, os_dir, dest = repo
        (common / "settings.json").write_text("{}", encoding="utf-8")
        assert not dest.exists()

        merge_directories(common, os_dir, dest)

        assert dest.exists()
