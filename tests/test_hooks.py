"""O guard e a aprovação humana. Os casos que importam rodam como o Claude Code roda:
processo novo, evento no stdin, `CLAUDE_PROJECT_DIR` no ambiente."""

from __future__ import annotations

import json

import pytest

from harness_hacka import hooks

from .conftest import cfg_of, decision, run_hook, write

ENV = "." + "env"  # evita o literal: hooks de segredo que leem comandos barram quem o cita


def denied(output: dict | None) -> bool:
    return bool(output) and output["hookSpecificOutput"]["permissionDecision"] == "deny"


def event(tool: str, session: str = "s1", **tool_input) -> dict:
    return {"session_id": session, "tool_name": tool, "tool_input": tool_input}


class TestSecrets:
    @pytest.mark.parametrize(
        "path", [ENV, f"backend/{ENV}", f"{ENV}.local", "chave.pem", "secrets/a.txt"]
    )
    def test_denies_reading_and_writing_secrets(self, project, path):
        cfg = cfg_of(project)
        assert denied(hooks.guard(event("Read", file_path=path), cfg))
        assert denied(hooks.guard(event("Write", file_path=path, content="x"), cfg))

    @pytest.mark.parametrize("path", [f"{ENV}.example", f"backend/{ENV}.sample", "README.md"])
    def test_allows_templates_and_regular_files(self, project, path):
        assert hooks.guard(event("Read", file_path=path), cfg_of(project)) is None

    def test_denies_command_reading_secret_and_allows_the_template(self, project):
        cfg = cfg_of(project)
        assert denied(hooks.guard(event("Bash", command=f"cat {ENV}"), cfg))
        assert hooks.guard(event("Bash", command=f"cp {ENV}.example {ENV}.sample"), cfg) is None

    def test_secrets_off_in_config(self, project):
        write(project, ".claude/harness-hacka.json", json.dumps({"guard": {"secrets": False}}))
        assert hooks.guard(event("Read", file_path=ENV), cfg_of(project)) is None

    def test_denies_writing_a_key_into_memory(self, project):
        key = "sk-ant-api03-" + "B" * 30
        output = hooks.guard(
            event("Write", file_path="memory/nota.md", content=f"a chave é {key}"), cfg_of(project)
        )
        assert denied(output)
        assert key not in json.dumps(output)  # a mensagem nunca repete o segredo

    def test_claude_md_counts_as_memory_even_with_absolute_path(self, project):
        key = "sk-ant-api03-" + "C" * 30
        target = str(project / "CLAUDE.md")
        if target[1:2] == ":":  # Windows: a ferramenta pode mandar a unidade em minúscula
            target = target[0].lower() + target[1:]
        assert denied(hooks.guard(event("Edit", file_path=target, new_string=key), cfg_of(project)))

    def test_key_outside_memory_is_not_the_guards_business(self, project):
        key = "sk-ant-api03-" + "B" * 30
        assert (
            hooks.guard(event("Write", file_path="src/x.py", content=key), cfg_of(project)) is None
        )


class TestMemoryIsNeverDeleted:
    @pytest.mark.parametrize(
        "command",
        [
            "rm memory/velha.md",
            "cd x && rm -rf memory/journal",
            "git rm memory/a.md",
            "Remove-Item memory\\a.md",
        ],
    )
    def test_denies_deleting(self, project, command):
        assert denied(hooks.guard(event("Bash", command=command), cfg_of(project)))

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf node_modules && ls memory/",
            "cat memory/decisions/0001-a.md 2>/dev/null",
            "grep -r rm memory/",
        ],
    )
    def test_does_not_confuse_with_something_else(self, project, command):
        assert hooks.guard(event("Bash", command=command), cfg_of(project)) is None


class TestHumanDecision:
    def accept(self, cfg, path, session="s1"):
        return hooks.guard(
            event(
                "Edit",
                session,
                file_path=str(path),
                old_string="status: proposed",
                new_string="status: accepted",
            ),
            cfg,
        )

    def test_agent_does_not_accept_alone(self, project):
        path = decision(project, 1, status="proposed", owner="")
        output = self.accept(cfg_of(project), path)
        assert denied(output)
        assert "accept 0001" in output["hookSpecificOutput"]["permissionDecisionReason"]

    def test_person_approves_in_the_prompt_and_the_edit_goes_through(self, project):
        cfg = cfg_of(project)
        path = decision(project, 1, status="proposed", owner="")
        output = hooks.approval({"session_id": "s1", "prompt": "li tudo, accept 0001"}, cfg)
        assert "aprovou a decisão 0001" in output["hookSpecificOutput"]["additionalContext"]
        assert self.accept(cfg, path) is None
        assert denied(self.accept(cfg, path, session="outra-sessao"))

    @pytest.mark.parametrize(
        "prompt",
        ["não aceito 0001", "do not accept 0001", "never approve 0001", "accept", "accept 0099"],
    )
    def test_prompt_that_does_not_approve(self, project, prompt):
        cfg = cfg_of(project)
        decision(project, 1, status="proposed", owner="")
        assert hooks.approval({"session_id": "s1", "prompt": prompt}, cfg) is None

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("accept 0003", [3]),
            ("aceito 0003", [3]),
            ("aprovo as decisões 0003 e 0004. Depois a 0005", [3, 4]),
            ("approve 0003 and 0004", [3, 4]),
            ("aceito a sugestão, mas não a 0003", []),
            ("accept 0002, except 0003", [2]),
            ("aceito tudo menos a 0004", []),
        ],
    )
    def test_approval_phrases(self, text, expected):
        assert hooks.approvals_in_text(text) == expected

    def test_writing_an_already_accepted_decision_also_needs_a_person(self, project):
        text = "---\nstatus: accepted\ndate: 2026-09-26\ndecided_by: Eu\n---\n# 0007: X\n"
        output = hooks.guard(
            event("Write", file_path="memory/decisions/0007-x.md", content=text), cfg_of(project)
        )
        assert denied(output)

    def test_proposed_to_rejected_does_not_need_approval(self, project):
        path = decision(project, 1, status="proposed", owner="")
        output = hooks.guard(
            event(
                "Edit",
                file_path=str(path),
                old_string="status: proposed",
                new_string="status: rejected",
            ),
            cfg_of(project),
        )
        assert output is None

    def test_approving_the_new_one_unlocks_superseding_the_old_one(self, project):
        cfg = cfg_of(project)
        old = decision(project, 1, title="Antiga", status="accepted")
        decision(project, 2, title="Nova", status="proposed", owner="", supersedes="0001")
        edit_old = event(
            "Edit",
            file_path=str(old),
            old_string="status: accepted",
            new_string="status: superseded",
        )
        assert denied(hooks.guard(edit_old, cfg))
        hooks.approval({"session_id": "s1", "prompt": "accept 0002"}, cfg)
        assert hooks.guard(edit_old, cfg) is None

    def test_changing_status_through_the_shell_is_denied(self, project):
        command = "sed -i 's/proposed/accepted/' memory/decisions/0001-x.md"
        assert denied(hooks.guard(event("Bash", command=command), cfg_of(project)))
        command = "echo status: accepted > memory/decisions/0001-x.md"
        assert denied(hooks.guard(event("Bash", command=command), cfg_of(project)))


class TestGitHooks:
    @pytest.mark.parametrize(
        "command",
        [
            "git commit --no-verify -m 'x'",
            "git commit -nm 'x'",
            "git commit -m 'x' -n",
            "git add . && git commit -an -m x",
            "HUSKY=0 git commit -m x",
            "git -c core.hooksPath=/dev/null commit -m x",
            "git push --no-verify origin main",
            "git -C web commit --no-verify",
        ],
    )
    def test_denies_skipping_git_hooks(self, project, command):
        output = hooks.guard(event("Bash", command=command), cfg_of(project))
        assert denied(output)
        assert "hooks do git" in output["hookSpecificOutput"]["permissionDecisionReason"]

    @pytest.mark.parametrize(
        "command",
        [
            "git commit -m 'nunca use --no-verify'",
            "git commit -m \"$(cat <<'EOF'\nnão use git commit --no-verify\nEOF\n)\"",
            "git commit -F - <<EOF\ngit commit -n\nEOF",
            "git commit -mnovo",
            "git commit --amend --no-edit",
            "git push -n origin main",
            "HUSKY=0 pnpm install",
            "grep -rn -- --no-verify .husky/",
        ],
    )
    def test_does_not_confuse_with_something_else(self, project, command):
        assert hooks.guard(event("Bash", command=command), cfg_of(project)) is None

    def test_forced_add_is_a_secrets_rule(self, project):
        cfg = cfg_of(project)
        assert denied(hooks.guard(event("Bash", command="git add -f web/dados.json"), cfg))
        assert denied(hooks.guard(event("Bash", command="git add --force x"), cfg))
        assert hooks.guard(event("Bash", command="git add -A"), cfg) is None

    def test_off_in_config(self, project):
        write(project, ".claude/harness-hacka.json", json.dumps({"guard": {"git_hooks": False}}))
        assert hooks.guard(event("Bash", command="git commit -n -m x"), cfg_of(project)) is None


class TestTriggers:
    def test_notices_once_per_session(self, project):
        write(project, ".claude/harness-hacka.json", json.dumps({"profile": "python"}))
        cfg = cfg_of(project)
        first = hooks.triggers(event("Edit", file_path="backend/pyproject.toml"), cfg)
        assert "/harness-hacka:decide" in first["hookSpecificOutput"]["additionalContext"]
        assert hooks.triggers(event("Edit", file_path="backend/pyproject.toml"), cfg) is None
        assert hooks.triggers(event("Edit", file_path="backend/app/main.py"), cfg) is None

    @pytest.mark.parametrize(
        ("rel", "glob", "expected"),
        [
            ("backend/pyproject.toml", "pyproject.toml", True),
            ("supabase/migrations/001.sql", "**/migrations/**", True),
            ("migrations/001.sql", "**/migrations/**", True),
            ("docker-compose.prod.yml", "docker-compose*.yml", True),
            (".github/workflows/ci.yml", ".github/workflows/**", True),
            ("src/pyproject.toml.bak", "pyproject.toml", False),
            ("web/prisma/schema.prisma", "**/prisma/schema.prisma", True),
            ("prisma/schema.prisma", "**/prisma/schema.prisma", True),
        ],
    )
    def test_glob(self, rel, glob, expected):
        assert hooks.matches(rel, glob) is expected

    def test_nextjs_profile_sees_the_schema_in_a_monorepo(self, project):
        write(project, ".claude/harness-hacka.json", json.dumps({"profile": "nextjs"}))
        out = hooks.triggers(event("Edit", file_path="web/prisma/schema.prisma"), cfg_of(project))
        assert "estrutura do banco" in out["hookSpecificOutput"]["additionalContext"]


class TestRealProcess:
    def test_gate_project_without_config_stays_silent(self, tmp_path, isolated_tmp):
        other = tmp_path / "other"
        other.mkdir()
        for name, ev in [
            ("guard", event("Read", file_path=ENV)),
            ("session-start", {"source": "startup"}),
            ("approval", {"prompt": "accept 0001"}),
            ("triggers", event("Edit", file_path="pyproject.toml")),
        ]:
            done = run_hook(name, {**ev, "cwd": str(other)}, other, isolated_tmp)
            assert (done.returncode, done.stdout) == (0, ""), name
        assert not (other / "memory").exists()

    def test_denies_for_real_with_the_json_the_platform_reads(self, project, isolated_tmp):
        done = run_hook("guard", event("Read", file_path=ENV), project, isolated_tmp)
        assert done.returncode == 0
        output = json.loads(done.stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_approval_crosses_processes_of_the_same_session(self, project, isolated_tmp):
        path = decision(project, 1, status="proposed", owner="")
        ev = event(
            "Edit",
            file_path=str(path),
            old_string="status: proposed",
            new_string="status: accepted",
        )
        assert json.loads(run_hook("guard", ev, project, isolated_tmp).stdout)
        run_hook("approval", {"session_id": "s1", "prompt": "accept 0001"}, project, isolated_tmp)
        assert run_hook("guard", ev, project, isolated_tmp).stdout == ""

    def test_session_start_injects_context(self, project, isolated_tmp):
        decision(project, 1, title="Supabase na nuvem")
        output = json.loads(
            run_hook("session-start", {"source": "startup"}, project, isolated_tmp).stdout
        )
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "0001 Supabase na nuvem" in output["hookSpecificOutput"]["additionalContext"]

    def test_invalid_config_warns_on_stderr_and_does_nothing(self, project, isolated_tmp):
        write(project, ".claude/harness-hacka.json", '{"housekeeping": {"stale": 1}}')
        done = run_hook("guard", event("Read", file_path=ENV), project, isolated_tmp)
        assert (done.returncode, done.stdout) == (0, "")
        assert "config inválida" in done.stderr

    def test_garbage_event_does_not_break(self, project, isolated_tmp):
        done = run_hook(
            "guard", {"tool_name": "Edit", "tool_input": "não é objeto"}, project, isolated_tmp
        )
        assert (done.returncode, done.stdout) == (0, "")
