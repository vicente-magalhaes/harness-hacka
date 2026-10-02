"""Os hooks do plugin. Um ponto de entrada: `harness-hacka hook <nome>`, lendo o evento do stdin.

Três regras valem para todos:

1. Sem `.claude/harness-hacka.json` no projeto, sai calado (o gate).
2. Nunca derruba a sessão. Qualquer exceção vira aviso no stderr e saída 0. Um harness de
   memória que quebra o trabalho custa mais do que entrega. A única saída diferente de 0 é o
   bloqueio, para o agente que bloqueia por código de saída (o Devin, com 2).
3. Proibição que importa é `deny`, não `ask`. O `ask` segue o modo da sessão e, em modo
   automático, pode passar sem ninguém ver. O `deny` bloqueia em qualquer modo.

O evento chega no dialeto do agente e é traduzido para o do Claude Code em `agents.py`. Daqui
para baixo, tudo fala um dialeto só.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from . import agents, config, sensitive, state
from . import frontmatter as fm
from .memory import field_key, normalize_status, parse_numbers

Event = dict[str, Any]

# Arquivos que um agente não lê nem escreve. Os modelos (.example e afins) são permitidos.
_SECRET_PATHS = (
    re.compile(r"(^|/)\.env(\.[^/]+)?$", re.IGNORECASE),
    re.compile(r"\.(pem|key|p12|pfx)$", re.IGNORECASE),
    re.compile(r"(^|/)secrets?/", re.IGNORECASE),
    re.compile(r"service[_-]?account[^/]*\.json$", re.IGNORECASE),
    re.compile(r"credentials[^/]*\.json$", re.IGNORECASE),
    re.compile(r"(^|/)id_(rsa|ed25519|ecdsa)$", re.IGNORECASE),
)
_TEMPLATE_SUFFIX = re.compile(r"\.(example|sample|template|exemplo)$", re.IGNORECASE)
_SAFE_ENV = re.compile(r"\.env\.(example|sample|template|exemplo)\b", re.IGNORECASE)
_ENV_IN_COMMAND = re.compile(r"(?<![\w-])\.env(\.[\w.-]+)?\b", re.IGNORECASE)
_SEPARATOR = re.compile(r"&&|\|\||;|\||\n")
_DELETE = re.compile(
    r"^\s*(?:sudo\s+)?(?:rm|rmdir|unlink|shred|del|erase|rd|remove-item|ri|git\s+rm)\b",
    re.IGNORECASE,
)
# Só verbos que escrevem no lugar ou movem. `cat` e `2>/dev/null` não contam: falso positivo
# ensina a ignorar a portaria.
_SHELL_WRITE = re.compile(
    r"\bsed\s+-i|\bperl\s+-[a-z]*i|\btee\b|\bset-content\b|\bout-file\b|\badd-content\b|"
    r"\b(?:mv|move|move-item|rename-item)\b|\barchive\b",
    re.IGNORECASE,
)
# "accept 0003" é a frase canônica; "approve", "aceito" e "aprovo" também valem.
_APPROVE = re.compile(r"\b(accept|approve|aceito|aprovo)\b", re.IGNORECASE)
_NEGATION_BEFORE = re.compile(
    r"\b(not|don'?t|do\s+not|never|n[aã]o|nunca|jamais|sem)\b\W*$", re.IGNORECASE
)
_NEGATION_BETWEEN = re.compile(
    r"\b(not|except|never|n[aã]o|nunca|jamais|exceto|menos)\b", re.IGNORECASE
)
_EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
_SHELL_TOOLS = ("Bash", "PowerShell")


# ----------------------------------------------------------------------------------------
# entrada


def run(name: str, agent: str = "") -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        action = HOOKS.get(name)
        if action is None:
            print(f"[harness-hacka] hook desconhecido: {name}", file=sys.stderr)
            return 0
        try:
            raw: Event = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            return 0
        if not isinstance(raw, dict):
            return 0
        root = _root(raw)
        if root is None:
            return 0
        try:
            cfg = config.load(root)
        except config.InvalidConfig as error:
            print(f"[harness-hacka] config inválida, hooks desligados: {error}", file=sys.stderr)
            return 0
        if cfg is None:
            return 0
        who = agents.detect(explicit=agent)
        state.record_event(name, who, raw)
        output = action({**agents.normalize(raw), AGENT_KEY: who}, cfg)
        stdout, stderr, code = agents.render(output, who)
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
        return code
    except Exception as error:  # noqa: BLE001 - hook nunca derruba a sessão
        print(f"[harness-hacka] hook {name} falhou e foi liberado: {error!r}", file=sys.stderr)
        return 0


# Chave que o `run` acrescenta ao evento para as ações saberem de qual agente ele veio.
AGENT_KEY = "harness_hacka_agent"


def _root(event: Event) -> Path | None:
    # Quem diz qual é o projeto é a plataforma. Cair no próximo candidato quando o primeiro não
    # tem config faria a política de um projeto agir dentro de outro (o cwd do processo pode
    # ser qualquer lugar). Só sem nenhuma indicação vale a pasta atual.
    given = (
        os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("DEVIN_PROJECT_DIR")
        or event.get("cwd")
    )
    return config.find_root(Path(str(given) if given else os.getcwd()))


def _context(event_name: str, text: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": text}}


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


# ----------------------------------------------------------------------------------------
# SessionStart e SubagentStart


def session_start(event: Event, cfg: config.Config) -> dict[str, Any] | None:
    from . import briefing
    from .memory import load

    # No Devin CLI, o mesmo projeto pode registrar o hook duas vezes: pelo plugin e pelo
    # `.devin/hooks.v1.json`, e o Devin roda os dois. Duas cópias do resumo são 12 mil chars.
    if event.get(AGENT_KEY) == agents.DEVIN and not state.once_within(
        str(event.get("session_id", "")), f"session-start:{event.get('source', '')}", 30
    ):
        return None
    return _context("SessionStart", briefing.build(load(cfg), date.today()))


def subagent_start(event: Event, cfg: config.Config) -> dict[str, Any] | None:
    from . import briefing
    from .memory import load

    return _context("SubagentStart", briefing.build(load(cfg), date.today(), subagent=True))


# ----------------------------------------------------------------------------------------
# UserPromptSubmit: a única porta pela qual uma pessoa aprova uma decisão


def approvals_in_text(text: str) -> list[int]:
    """`accept 0003` e `aprovo as decisões 0003 e 0004` aprovam; `não aceito 0003`, não."""
    found: list[int] = []
    for match in _APPROVE.finditer(text):
        if _NEGATION_BEFORE.search(text[max(0, match.start() - 16) : match.start()]):
            continue
        stretch = re.split(r"[\n.;!?]", text[match.end() : match.end() + 80], maxsplit=1)[0]
        for number in re.finditer(r"\b(\d{4})\b", stretch):
            # "aceito a sugestão, mas não a 0003": negação entre o verbo e o número não aprova.
            if _NEGATION_BETWEEN.search(stretch[: number.start()]):
                break
            found.append(int(number.group(1)))
    return sorted(set(found))


def approval(event: Event, cfg: config.Config) -> dict[str, Any] | None:
    if not cfg.human_decisions:
        return None
    existing = (
        {int(p.name[:4]) for p in cfg.decisions.glob("[0-9][0-9][0-9][0-9]-*.md")}
        if cfg.decisions.is_dir()
        else set()
    )
    approved = [n for n in approvals_in_text(str(event.get("prompt", ""))) if n in existing]
    if not approved:
        return None
    state.record_approval(str(event.get("session_id", "")), approved)
    from . import git

    who = git.user_name(cfg.root) or "o nome da pessoa"
    numbers = ", ".join(f"{n:04d}" for n in approved)
    return _context(
        "UserPromptSubmit",
        f"[harness-hacka] A pessoa aprovou a decisão {numbers} nesta mensagem. Agora a edição "
        f"passa: marque `status: accepted`, `decided_by: {who}` e mantenha a `date`. Se ela "
        "substitui outra, marque a antiga como superseded nos dois lados. A aprovação vale "
        "por 30 minutos nesta sessão.",
    )


# ----------------------------------------------------------------------------------------
# PreToolUse: o guard


def _path(cfg: config.Config, raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = cfg.root / path
    return Path(os.path.normpath(path))


def _inside(path: Path, folder: Path) -> bool:
    p = os.path.normcase(str(path))
    f = os.path.normcase(str(Path(os.path.normpath(folder))))
    return p == f or p.startswith(f + os.sep)


def _rel(cfg: config.Config, path: Path) -> str:
    # relpath e não relative_to: no Windows, `c:\` e `C:\` são a mesma pasta, e a ferramenta
    # nem sempre manda a letra da unidade como a plataforma manda a raiz do projeto.
    try:
        rel = os.path.relpath(str(path), str(cfg.root))
    except ValueError:  # outra unidade
        return path.as_posix()
    return path.as_posix() if rel.startswith("..") else Path(rel).as_posix()


def is_secret(rel: str) -> bool:
    normal = rel.replace("\\", "/")
    if _TEMPLATE_SUFFIX.search(normal):
        return False
    return any(p.search(normal) for p in _SECRET_PATHS)


def command_touches_secret(command: str) -> bool:
    clean = _SAFE_ENV.sub("", command)
    if _ENV_IN_COMMAND.search(clean):
        return True
    return any(is_secret(word) for word in re.findall(r"[^\s\"'=<>|;&()]+", clean))


def _new_texts(tool_input: dict[str, Any]) -> list[str]:
    if "content" in tool_input:
        return [str(tool_input.get("content") or "")]
    if "new_string" in tool_input:
        return [str(tool_input.get("new_string") or "")]
    return [str(e.get("new_string") or "") for e in tool_input.get("edits") or []]


def _text_after(current: str, tool_input: dict[str, Any], tool: str) -> str:
    if tool == "Write":
        return str(tool_input.get("content") or "")
    edits = tool_input.get("edits") if tool == "MultiEdit" else [tool_input]
    text = current
    for e in edits or []:
        old, new = str(e.get("old_string") or ""), str(e.get("new_string") or "")
        if old and old in text:
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def _status(text: str) -> str:
    if not text:
        return ""
    try:
        fields, _ = fm.split(text)
    except fm.InvalidFrontmatter:
        return ""
    return normalize_status(fm.text(fields, "status"))


def _unlocked(cfg: config.Config, session: str) -> set[int]:
    """Aprovadas pela pessoa, mais as que uma aprovada declara substituir."""
    approved = state.approvals(session)
    unlocked = set(approved)
    for n in approved:
        for path in cfg.decisions.glob(f"{n:04d}-*.md"):
            try:
                fields, _ = fm.split(path.read_text(encoding="utf-8-sig"))
            except (OSError, fm.InvalidFrontmatter):
                continue
            unlocked |= set(parse_numbers(fm.as_list(fields, field_key(fields, "supersedes"))))
    return unlocked


def _status_change(
    cfg: config.Config, target: Path, tool_input: dict[str, Any], tool: str, session: str
) -> str | None:
    if not re.match(r"^\d{4}-", target.name) or target.suffix.lower() != ".md":
        return None
    current = target.read_text(encoding="utf-8-sig") if target.is_file() else ""
    before, after = _status(current), _status(_text_after(current, tool_input, tool))
    if before == after or "accepted" not in (before, after):
        return None
    return _locked(cfg, int(target.name[:4]), after, session)


def _secret_file(rel: str) -> str:
    return (
        f"`{rel}` parece arquivo de segredo (.env, chave, credencial). Agente não lê nem "
        "escreve segredo. Documente a variável no .env.example e peça para uma pessoa cuidar "
        "do valor real."
    )


def _secret_in_memory(kinds: list[str], rel: str) -> str:
    return (
        f"Isto gravaria {', '.join(kinds)} em `{rel}`. Memória não guarda segredo: escreva o "
        "nome da variável, nunca o valor."
    )


def _in_memory(cfg: config.Config, target: Path) -> bool:
    return _inside(target, cfg.memory) or any(
        _inside(target, cfg.root / f) for f in cfg.index_files
    )


def _locked(cfg: config.Config, number: int, after: str, session: str) -> str | None:
    if number in _unlocked(cfg, session):
        return None
    verb = "Aceitar" if after == "accepted" else "Tirar de accepted"
    return (
        f"{verb} a decisão {number:04d} é ato de uma pessoa, e o harness-hacka não deixa o "
        f"agente fazer isso sozinho. Mostre à pessoa o resumo da decisão e peça que ela "
        f"responda `accept {number:04d}` no chat. Depois disso, repita esta edição."
    )


_STATUS_LINE = re.compile(r"^\s*status\s*:\s*(.*?)\s*$", re.IGNORECASE)


def _patch_status_change(
    cfg: config.Config, target: Path, change: agents.FileChange, session: str
) -> str | None:
    """Patch não dá o texto final, só as linhas que entram e saem. Basta uma linha de status
    com `accepted` de um lado só para a mudança precisar de uma pessoa."""
    if not re.match(r"^\d{4}-", target.name) or target.suffix.lower() != ".md":
        return None

    def statuses(lines: list[str]) -> set[str]:
        return {normalize_status(m.group(1)) for m in map(_STATUS_LINE.match, lines) if m}

    added, removed = statuses(change.added), statuses(change.removed)
    if "accepted" not in added ^ removed:
        return None
    return _locked(cfg, int(target.name[:4]), "accepted" if "accepted" in added else "", session)


def _guard_patch(cfg: config.Config, patch: str, session: str) -> dict[str, Any] | None:
    for raw, change in agents.parse_patch(patch).items():
        target = _path(cfg, raw)
        rel = _rel(cfg, target)
        if cfg.guard_secrets and is_secret(rel):
            return _deny(_secret_file(rel))
        if change.deleted and _inside(target, cfg.memory):
            return _deny(_MEMORY_IS_ARCHIVED)
        if cfg.guard_memory_secrets and _in_memory(cfg, target):
            kinds = sorted(sensitive.find_secrets("\n".join(change.added)))
            if kinds:
                return _deny(_secret_in_memory(kinds, rel))
        if cfg.human_decisions and _inside(target, cfg.decisions):
            reason = _patch_status_change(cfg, target, change, session)
            if reason:
                return _deny(reason)
    return None


_MEMORY_IS_ARCHIVED = (
    "Memória não se apaga, se arquiva. Use `harness-hacka archive <caminho> --reason "
    '"..."`: o arquivo sai do caminho e o histórico fica.'
)

# Texto entre aspas e corpo de heredoc saem antes de procurar `--no-verify`: a mensagem de
# commit "nunca use --no-verify" não pula hook nenhum, e negá-la ensina a ignorar o guard.
_QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.DOTALL | re.MULTILINE)
_GIT = re.compile(
    r"^\s*(?P<env>(?:[A-Za-z_]\w*=\S*\s+)*)(?:sudo\s+)?git"
    r"(?P<opts>(?:\s+(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?))*)\s+(?P<sub>[\w-]+)(?P<rest>.*)$"
)
_HOOKS_OFF_ENV = re.compile(r"\bHUSKY=0\b|\bHUSKY_SKIP_HOOKS=1\b")
# Opções curtas do `git commit` que levam valor: o que vem colado depois delas é o valor, não
# outra opção. `-mnovo` é a mensagem "novo", não `-n`.
_COMMIT_VALUE_FLAGS = set("mFCctS")


def _short_flag(rest: str, flag: str, value_flags: set[str]) -> bool:
    for cluster in re.findall(r"(?:^|\s)-([A-Za-z][\w]*)", rest):
        for char in cluster:
            if char == flag:
                return True
            if char in value_flags:
                break
    return False


_SKIPS_GIT_HOOKS = (
    "Isto pula os hooks do git (`--no-verify`, `-n` no commit, `HUSKY=0` ou `core.hooksPath`). "
    "Eles são a checagem que roda antes do código sair daqui. Se o hook reprovou, corrija o "
    "que ele acusou; se o hook está errado, peça para uma pessoa decidir."
)
_FORCED_ADD = (
    "`git add --force` passa por cima do .gitignore, que é o que segura segredo fora do git. "
    "Se o arquivo deve mesmo ir para o git, tire-o do .gitignore numa mudança à parte, que "
    "uma pessoa revisa."
)


def _skips_hooks(git: re.Match[str]) -> bool:
    sub, rest = git.group("sub"), git.group("rest")
    if sub not in ("commit", "push"):
        return False
    return bool(
        "--no-verify" in rest.split()
        or (sub == "commit" and _short_flag(rest, "n", _COMMIT_VALUE_FLAGS))
        or _HOOKS_OFF_ENV.search(git.group("env"))
        or "core.hookspath" in git.group("opts").casefold()
    )


def _forces_add(git: re.Match[str]) -> bool:
    rest = git.group("rest")
    return git.group("sub") == "add" and (
        "--force" in rest.split() or _short_flag(rest, "f", set())
    )


def _git_bypass(command: str, secrets: bool, hooks: bool) -> str | None:
    clean = _QUOTED.sub("''", _HEREDOC.sub("", command))
    for piece in _SEPARATOR.split(clean):
        git = _GIT.match(piece)
        if git and hooks and _skips_hooks(git):
            return _SKIPS_GIT_HOOKS
        if git and secrets and _forces_add(git):
            return _FORCED_ADD
    return None


def guard(event: Event, cfg: config.Config) -> dict[str, Any] | None:
    tool = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    session = str(event.get("session_id", ""))

    if tool == "ApplyPatch":
        return _guard_patch(cfg, str(tool_input.get("patch") or ""), session)

    if tool in (*_EDIT_TOOLS, "Read"):
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not raw:
            return None
        target = _path(cfg, str(raw))
        rel = _rel(cfg, target)
        if cfg.guard_secrets and is_secret(rel):
            return _deny(_secret_file(rel))
        if tool == "Read":
            return None
        if cfg.guard_memory_secrets and _in_memory(cfg, target):
            kinds = sorted({k for t in _new_texts(tool_input) for k in sensitive.find_secrets(t)})
            if kinds:
                return _deny(_secret_in_memory(kinds, rel))
        if cfg.human_decisions and _inside(target, cfg.decisions):
            reason = _status_change(cfg, target, tool_input, tool, session)
            if reason:
                return _deny(reason)
        return None

    if tool in _SHELL_TOOLS:
        command = str(tool_input.get("command", ""))
        if cfg.guard_secrets and command_touches_secret(command):
            return _deny(
                "Este comando mexe com arquivo de segredo (.env, chave, credencial). Operação "
                "com segredo real não passa por agente: peça para uma pessoa rodar."
            )
        bypass = _git_bypass(command, cfg.guard_secrets, cfg.guard_git_hooks)
        if bypass:
            return _deny(bypass)
        folder = re.escape(cfg.memory_dir)
        in_memory = re.compile(rf"(^|[\s\"'=/\\]){folder}([/\\\s\"']|$)")
        in_decisions = re.compile(rf"{folder}[/\\]+decisions([/\\\s\"']|$)")
        redirects = re.compile(rf">{{1,2}}\s*[\"']?[^\s\"'|;&]*{folder}[/\\]+decisions")
        for piece in _SEPARATOR.split(command):
            if _DELETE.search(piece) and in_memory.search(piece):
                return _deny(_MEMORY_IS_ARCHIVED)
            if cfg.human_decisions and (
                (in_decisions.search(piece) and _SHELL_WRITE.search(piece))
                or redirects.search(piece)
            ):
                return _deny(
                    "Decisão se edita pela ferramenta de edição, não pelo shell: é assim que o "
                    "guard confere quem muda o status. Decisão também não se arquiva."
                )
    return None


# ----------------------------------------------------------------------------------------
# PostToolUse: gatilhos de decisão


def matches(rel: str, glob: str) -> bool:
    """Glob no estilo gitignore: sem `/`, casa com o nome em qualquer pasta; `**` atravessa."""
    rel = rel.replace("\\", "/")
    target = rel if "/" in glob else rel.rsplit("/", 1)[-1]
    regex = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            regex += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            regex += ".*"
            i += 2
        elif glob[i] == "*":
            regex += "[^/]*"
            i += 1
        elif glob[i] == "?":
            regex += "[^/]"
            i += 1
        else:
            regex += re.escape(glob[i])
            i += 1
    return re.fullmatch(regex, target, re.IGNORECASE) is not None


def triggers(event: Event, cfg: config.Config) -> dict[str, Any] | None:
    if not cfg.triggers:
        return None
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None
    if event.get("tool_name") == "ApplyPatch":
        paths = list(agents.parse_patch(str(tool_input.get("patch") or "")))
    else:
        paths = [tool_input["file_path"]] if tool_input.get("file_path") else []
    session = str(event.get("session_id", ""))
    for raw in paths:
        target = _path(cfg, str(raw))
        if _inside(target, cfg.memory):
            continue
        rel = _rel(cfg, target)
        for glob, reason in cfg.triggers.items():
            if matches(rel, glob) and state.first_time(session, f"trigger:{glob}"):
                return _context(
                    "PostToolUse",
                    f"[harness-hacka] `{rel}` mudou. Esse arquivo costuma carregar decisão "
                    f"({reason}). Se esta mudança é uma escolha nova e não óbvia, ofereça "
                    "registrar com `/harness-hacka:decide`. Se é rotina, siga sem comentar.",
                )
    return None


HOOKS = {
    "session-start": session_start,
    "subagent-start": subagent_start,
    "approval": approval,
    "guard": guard,
    "triggers": triggers,
}
