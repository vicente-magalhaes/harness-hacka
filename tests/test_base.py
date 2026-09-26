"""Frontmatter, markdown e config: as peças que todo o resto presume."""

from __future__ import annotations

import json
from datetime import date

import pytest

from harness_hacka import config
from harness_hacka import frontmatter as fm
from harness_hacka import markdown as md

from .conftest import write


class TestFrontmatter:
    def test_scalar_inline_list_and_block_list(self):
        fields, body = fm.split(
            "---\nstatus: accepted  # comentário\nsupersedes: [0002, 0003]\ntags:\n  - a\n  - b\n"
            'title: "com # dentro"\n---\n# Corpo\n'
        )
        assert fields == {
            "status": "accepted",
            "supersedes": ["0002", "0003"],
            "tags": ["a", "b"],
            "title": "com # dentro",
        }
        assert body == "# Corpo\n"

    def test_without_frontmatter_returns_whole_text(self):
        assert fm.split("# Só corpo\n") == ({}, "# Só corpo\n")

    def test_unclosed_frontmatter_is_an_error(self):
        with pytest.raises(fm.InvalidFrontmatter):
            fm.split("---\nstatus: accepted\n# esqueceram de fechar\n")

    def test_line_outside_the_format_is_an_error(self):
        with pytest.raises(fm.InvalidFrontmatter):
            fm.split("---\nisto não é chave valor\n---\n")

    def test_empty_key_is_empty_text(self):
        fields, _ = fm.split("---\ndecided_by:\ndate: 2026-09-26\n---\n")
        assert fm.text(fields, "decided_by") == ""
        assert fm.text(fields, "date") == "2026-09-26"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("2026-09-26", date(2026, 9, 26)), ("26/09/2026", date(2026, 9, 26)), ("amanhã", None)],
    )
    def test_dates(self, raw, expected):
        assert fm.parse_date(raw) == expected

    def test_set_field_replaces_or_appends_keeping_the_rest(self):
        text = "---\na: 1\nb: 2\n---\n# T\n"
        assert fm.set_field(text, "b", "3") == "---\na: 1\nb: 3\n---\n# T\n"
        assert fm.set_field(text, "c", "4") == "---\na: 1\nb: 2\nc: 4\n---\n# T\n"
        assert fm.set_field("# T\n", "a", "1") == "---\na: 1\n---\n\n# T\n"


class TestMarkdown:
    def test_section_ignores_heading_inside_fence(self):
        body = "# T\n\n```markdown\n## Falsa\n- não\n```\n\n## Real\n- sim\n"
        assert md.section(body, "Falsa") is None
        assert md.list_items(md.section(body, "Real")) == ["sim"]

    def test_unclosed_fence_does_not_swallow_the_file(self):
        body = "## Seção\n- item\n```\nsem fechar\n"
        assert md.list_items(md.section(body, "Seção")) == ["item"]

    def test_item_with_indented_continuation(self):
        assert md.list_items(["- primeira linha", "  continua aqui", "- outro"]) == [
            "primeira linha continua aqui",
            "outro",
        ]

    def test_relative_links_ignore_url_anchor_and_code(self):
        body = (
            "[a](notas/a.md) [b](https://x.com) [c](#topo) `[d](d.md)` "
            "[e](README.md#como-rodar) ![img](img.png)\n```\n[f](f.md)\n```\n"
        )
        assert md.relative_links(body) == [(1, "notas/a.md"), (1, "README.md")]


class TestConfig:
    def test_missing_file_is_the_gate(self, tmp_path):
        assert config.load(tmp_path) is None

    def test_invalid_json_is_loud(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", "{ não é json")
        with pytest.raises(config.InvalidConfig, match="JSON"):
            config.load(tmp_path)

    def test_unknown_key_is_loud_even_inside_a_section(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", json.dumps({"housekeeping": {"stale": 3}}))
        with pytest.raises(config.InvalidConfig, match="housekeeping.stale"):
            config.load(tmp_path)

    def test_wrong_type_is_loud(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", json.dumps({"guard": {"secrets": "yes"}}))
        with pytest.raises(config.InvalidConfig, match="true ou false"):
            config.load(tmp_path)

    def test_dollar_key_is_an_annotation(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", json.dumps({"$comment": "oi"}))
        assert config.load(tmp_path) is not None

    def test_profile_applies_and_project_wins(self, tmp_path):
        data = {
            "profile": "python",
            "triggers": {"pyproject.toml": None, "supabase/**": "banco"},
            "verify": ["make test"],
        }
        write(tmp_path, ".claude/harness-hacka.json", json.dumps(data))
        cfg = config.load(tmp_path)
        assert cfg is not None
        assert "pyproject.toml" not in cfg.triggers  # null desliga o gatilho herdado
        assert cfg.triggers["supabase/**"] == "banco"
        assert "Dockerfile*" in cfg.triggers  # herdado do perfil
        assert cfg.verify == ("make test",)
        assert "[HIPÓTESE]" in cfg.markers

    def test_unknown_profile_lists_the_available_ones(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", json.dumps({"profile": "cobol"}))
        with pytest.raises(config.InvalidConfig, match="nextjs"):
            config.load(tmp_path)

    def test_every_profile_is_valid(self, tmp_path):
        for name in config.available_profiles():
            write(tmp_path, ".claude/harness-hacka.json", json.dumps({"profile": name}))
            assert config.load(tmp_path) is not None

    def test_find_root_walks_up(self, tmp_path):
        write(tmp_path, ".claude/harness-hacka.json", "{}")
        (tmp_path / "a" / "b").mkdir(parents=True)
        assert config.find_root(tmp_path / "a" / "b") == tmp_path.resolve()
