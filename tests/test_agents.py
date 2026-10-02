"""O adaptador por agente: o evento do Devin chega traduzido, e o bloqueio sai no formato dele.

Os casos de processo rodam como o Devin roda: processo novo, evento no stdin,
`DEVIN_PROJECT_DIR` e `CLAUDE_PROJECT_DIR` no ambiente (o Devin passa os dois)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_hacka import agents, hooks, state
from harness_hacka.cli import main

from .conftest import LAUNCHER, cfg_of, decision, write

ENV = "." + "env"  # evita o literal: hooks de segredo que leem comandos barram quem o cita
KEY = "sk-ant-api03-" + "D" * 30


def devin(tool: str, session: str = "d1", **tool_input) -> dict:
    return {"session_id": session, "tool_name": tool, "tool_input": tool_input}


def guard(event: dict, cfg):
    return hooks.guard(agents.normalize(event), cfg)


def denied(output: dict | None) -> bool:
    return bool(output) and output["hookSpecificOutput"]["permissionDecision"] == "deny"


def run_devin(name: str, event: dict, root: Path, tmp: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env |= {"DEVIN_PROJECT_DIR": str(root), "CLAUDE_PROJECT_DIR": str(root)}
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(tmp)
    return subprocess.run(
        [sys.executable, str(LAUNCHER), "hook", name],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
        check=False,
    )


class TestNormalize:
    @pytest.mark.parametrize(
        ("event", "tool", "expected"),
        [
            (devin("read", path="a.md"), "Read", {"file_path": "a.md"}),
            (devin("write", file="a.md", contents="x"), "Write", {"file_path": "a.md"}),
            (devin("edit", path="a.md", old_str="x", new_str="y"), "Edit", {"old_string": "x"}),
            (devin("edit", path="a.md", edits=[]), "MultiEdit", {"file_path": "a.md"}),
            (devin("exec", command="ls", shell_id="main"), "Bash", {"command": "ls"}),
            (
                devin("apply_patch", input="*** Begin Patch"),
                "ApplyPatch",
                {"patch": "*** Begin Patch"},
            ),
        ],
    )
    def test_devin_tools_become_the_core_dialect(self, event, tool, expected):
        out = agents.normalize(event)
        assert out["tool_name"] == tool
        assert expected.items() <= out["tool_input"].items()

    def test_claude_event_passes_untouched(self):
        event = {"tool_name": "Edit", "tool_input": {"file_path": "a", "new_string": "b"}}
        assert agents.normalize(event) == event

    def test_unknown_tool_passes_untouched(self):
        event = devin("grep", pattern="x")
        assert agents.normalize(event) == event

    @pytest.mark.parametrize(
        ("env", "explicit", "expected"),
        [
            ({}, "", "claude"),
            ({"DEVIN_PROJECT_DIR": "/p", "CLAUDE_PROJECT_DIR": "/p"}, "", "devin"),
            ({}, "devin", "devin"),
            ({"DEVIN_PROJECT_DIR": "/p"}, "claude", "claude"),
        ],
    )
    def test_detect(self, env, explicit, expected):
        assert agents.detect(env, explicit) == expected


class TestPatch:
    def test_codex_format(self):
        patch = (
            "*** Begin Patch\n*** Add File: novo.md\n+linha\n"
            "*** Update File: velho.md\n@@\n-status: proposed\n+status: accepted\n"
            "*** Delete File: some.md\n*** End Patch\n"
        )
        files = agents.parse_patch(patch)
        assert set(files) == {"novo.md", "velho.md", "some.md"}
        assert files["novo.md"].created and files["novo.md"].added == ["linha"]
        assert files["velho.md"].removed == ["status: proposed"]
        assert files["some.md"].deleted

    def test_unified_diff(self):
        patch = (
            "--- a/x.md\n+++ b/x.md\n@@ -1 +1 @@\n-a\n+b\n"
            "--- a/y.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-c\n"
        )
        files = agents.parse_patch(patch)
        assert files["x.md"].added == ["b"] and files["x.md"].removed == ["a"]
        assert files["y.md"].deleted


class TestDevinGuard:
    def test_secrets_by_file_tool_and_by_shell(self, project):
        cfg = cfg_of(project)
        assert denied(guard(devin("read", path=f"web/{ENV}"), cfg))
        assert denied(guard(devin("exec", command=f"cat {ENV}"), cfg))
        assert guard(devin("read", path="README.md"), cfg) is None

    def test_patch_cannot_accept_a_decision_until_the_person_approves(self, project):
        cfg = cfg_of(project)
        decision(project, 1, status="proposed", owner="")
        patch = (
            "*** Begin Patch\n*** Update File: memory/decisions/0001-uma-decisao.md\n@@\n"
            "-status: proposed\n+status: accepted\n*** End Patch\n"
        )
        output = guard(devin("apply_patch", patch=patch), cfg)
        assert denied(output)
        assert "accept 0001" in output["hookSpecificOutput"]["permissionDecisionReason"]
        hooks.approval({"session_id": "d1", "prompt": "accept 0001"}, cfg)
        assert guard(devin("apply_patch", patch=patch), cfg) is None

    def test_patch_that_keeps_the_status_is_not_a_status_change(self, project):
        decision(project, 1, status="accepted")
        patch = (
            "*** Update File: memory/decisions/0001-uma-decisao.md\n"
            "-decided_by: Pessoa\n+decided_by: Pessoa Silva\n"
        )
        assert guard(devin("apply_patch", patch=patch), cfg_of(project)) is None

    def test_patch_writing_a_key_into_memory_or_deleting_memory(self, project):
        cfg = cfg_of(project)
        add_key = f"*** Add File: memory/nota.md\n+a chave é {KEY}\n"
        assert denied(guard(devin("apply_patch", patch=add_key), cfg))
        delete = "*** Delete File: memory/nota.md\n"
        assert denied(guard(devin("apply_patch", patch=delete), cfg))
        ordinary = "*** Update File: src/app.ts\n-a\n+b\n"
        assert guard(devin("apply_patch", patch=ordinary), cfg) is None

    def test_trigger_from_a_patch(self, project):
        write(project, ".claude/harness-hacka.json", json.dumps({"profile": "nextjs"}))
        patch = "*** Update File: web/prisma/schema.prisma\n-a\n+b\n"
        out = hooks.triggers(agents.normalize(devin("apply_patch", patch=patch)), cfg_of(project))
        assert "estrutura do banco" in out["hookSpecificOutput"]["additionalContext"]


class TestDevinProcess:
    def test_blocks_with_exit_2_reason_on_stderr_and_decision_json(self, project, isolated_tmp):
        done = run_devin("guard", devin("read", path=ENV), project, isolated_tmp)
        assert done.returncode == 2
        assert json.loads(done.stdout)["decision"] == "block"
        assert "segredo" in done.stderr

    def test_allows_silently(self, project, isolated_tmp):
        done = run_devin("guard", devin("read", path="README.md"), project, isolated_tmp)
        assert (done.returncode, done.stdout, done.stderr) == (0, "", "")

    def test_session_start_once_even_if_registered_twice(self, project, isolated_tmp):
        decision(project, 1, title="Supabase na nuvem")
        ev = {"session_id": "d9", "source": "startup"}
        first = run_devin("session-start", ev, project, isolated_tmp)
        assert "0001 Supabase na nuvem" in first.stdout
        assert run_devin("session-start", ev, project, isolated_tmp).stdout == ""

    def test_events_keep_only_key_names(self, project, isolated_tmp, capsys):
        run_devin("guard", devin("write", path="a.md", content=KEY), project, isolated_tmp)
        assert KEY not in (isolated_tmp / "harness-hacka" / state.EVENTS_FILE).read_text("utf-8")
        assert main(["events", "--json"]) == 0
        last = json.loads(capsys.readouterr().out)[-1]
        assert (last["agent"], last["hook"], last["tool_name"]) == ("devin", "guard", "write")
        assert last["tool_input_keys"] == ["content", "path"]
        assert "DEVIN_PROJECT_DIR" in last["env"]


def test_init_for_devin_writes_its_files_once(tmp_path, capsys):
    root = tmp_path / "novo"
    root.mkdir()
    assert main(["--project", str(root), "init", "--profile", "nextjs", "--agent", "devin"]) == 0
    out = capsys.readouterr().out
    assert "criado: .devin/config.json" in out and "criado: .devin/hooks.v1.json" in out
    config = json.loads((root / ".devin/config.json").read_text(encoding="utf-8"))
    assert config["requiredPlugins"] == ["vicente-magalhaes/harness-hacka"]
    hooks_file = json.loads((root / ".devin/hooks.v1.json").read_text(encoding="utf-8"))
    pre = hooks_file["PreToolUse"][0]
    assert "exec" in pre["matcher"] and "hook guard --agent devin" in pre["hooks"][0]["command"]

    (root / ".devin/config.json").write_text('{"requiredPlugins": ["outro/plugin"]}', "utf-8")
    main(["--project", str(root), "init", "--agent", "devin"])
    assert "já existe, não mexi: .devin/config.json" in capsys.readouterr().out
    assert "outro/plugin" in (root / ".devin/config.json").read_text(encoding="utf-8")
