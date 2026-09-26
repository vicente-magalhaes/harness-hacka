"""`harness-hacka`: o lado determinístico do harness. As skills chamam isto; o CI também.

harness-hacka status [--json]              estado da memória e candidatos do housekeeping
harness-hacka check [--json] [--strict]    auditoria; sai 1 se houver erro
harness-hacka briefing [--subagent]        o bloco que o início de sessão injeta
harness-hacka index [--update]             índices gerados a partir dos arquivos
harness-hacka new decision "Título"        próxima decisão, a partir do modelo
harness-hacka new journal "Título"         registro do diário desta sessão
harness-hacka new housekeeping             registro de um housekeeping
harness-hacka archive CAMINHO --reason M   tira da memória ativa sem apagar
harness-hacka init [--profile P]           config e esqueleto da memória (não sobrescreve)
harness-hacka profiles                     perfis de stack disponíveis
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

from . import __version__, config


def _project(args: argparse.Namespace) -> config.Config:
    root: Path | None = (
        Path(args.project).resolve() if args.project else config.find_root(Path.cwd())
    )
    if root is None or not (root / config.CONFIG_FILE).is_file():
        where = root or Path.cwd()
        raise SystemExit(
            f"harness-hacka: {where} não adotou o harness (falta "
            f"{config.CONFIG_FILE.as_posix()}).\n"
            "Rode `/harness-hacka:init` no Claude Code ou `harness-hacka init` aqui."
        )
    try:
        cfg = config.load(root)
    except config.InvalidConfig as error:
        raise SystemExit(f"harness-hacka: config inválida: {error}") from None
    assert cfg is not None
    return cfg


def _memory(args: argparse.Namespace):  # type: ignore[no-untyped-def]
    from .memory import load

    return load(_project(args))


def cmd_status(args: argparse.Namespace) -> int:
    from . import overview

    data = overview.build(_memory(args), date.today(), datetime.now())
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else overview.render(data))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    from . import git
    from .checks import audit
    from .memory import plural

    memory = _memory(args)
    cfg = memory.cfg
    changed = git.last_changed(cfg.root, cfg.memory.relative_to(cfg.root))
    findings = audit(memory, date.today(), changed)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in errors + warnings:
            print(f.format())
        if not cfg.memory.is_dir():
            print(f"x {cfg.memory_dir}/ não existe. Rode `harness-hacka init`.")
        total = (
            f"{plural(len(errors), 'erro', 'erros')}, {plural(len(warnings), 'aviso', 'avisos')}"
        )
        print(("ok, a memória confere" if not errors else "reprovado") + f" ({total})")
    failed = bool(errors) or (args.strict and bool(warnings)) or not cfg.memory.is_dir()
    return 1 if failed else 0


def cmd_briefing(args: argparse.Namespace) -> int:
    from . import briefing

    text = briefing.build(_memory(args), date.today(), subagent=args.subagent)
    print(text, end="")
    print(f"\n({len(text)} chars)", file=sys.stderr)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    from . import index

    memory = _memory(args)
    root = memory.cfg.root
    if args.update:
        written = index.update(memory)
        for path in written:
            print(f"atualizado: {path.relative_to(root).as_posix()}")
        if not written:
            print("índices em dia")
        return 0
    print(index.notes_table(memory, root))
    if memory.decisions:
        print()
        print(index.decisions_table(memory, root))
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    from . import git, scaffold

    memory = _memory(args)
    cfg = memory.cfg
    author = args.author or git.user_name(cfg.root)
    if args.kind in ("decision", "journal") and not args.title:
        raise SystemExit(f"harness-hacka: diga o título ({args.kind})")
    if args.kind == "decision":
        created = scaffold.new_decision(memory, args.title, date.today())
    elif args.kind == "journal":
        created = scaffold.new_entry(memory, args.title, author, datetime.now())
    else:
        created = scaffold.new_housekeeping(memory, author, datetime.now())
    print(created.relative_to(cfg.root).as_posix())
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    from .archive import NotArchivable, archive

    memory = _memory(args)
    try:
        target = archive(memory, args.path, args.reason, date.today())
    except NotArchivable as error:
        raise SystemExit(f"harness-hacka: {error}") from None
    print(target.relative_to(memory.cfg.root.resolve()).as_posix())
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    from . import scaffold

    root = Path(args.project).resolve() if args.project else Path.cwd().resolve()
    if args.profile and args.profile not in config.available_profiles():
        options = ", ".join(config.available_profiles())
        raise SystemExit(
            f"harness-hacka: perfil '{args.profile}' não existe. Disponíveis: {options}"
        )
    created = scaffold.skeleton(root, args.memory_dir, args.name or root.name, args.profile or "")
    for c in created:
        print(f"criado: {c.relative_to(root).as_posix()}")
    if not created:
        print("nada a criar: tudo já existe")
    cfg = config.load(root)
    if cfg is not None:
        from . import index
        from .memory import load

        for path in index.update(load(cfg)):
            print(f"índice gerado: {path.relative_to(cfg.root).as_posix()}")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    for name in config.available_profiles():
        data = json.loads((config.PROFILES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        print(f"{name:10} {data.get('description', '')}")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="harness-hacka", description="Memória de projeto para agentes de código."
    )
    p.add_argument("--version", action="version", version=f"harness-hacka {__version__}")
    p.add_argument("--project", help="raiz do projeto (padrão: sobe a partir da pasta atual)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="estado da memória")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("check", help="auditoria da memória")
    s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true", help="aviso também reprova")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("briefing", help="bloco do início de sessão")
    s.add_argument("--subagent", action="store_true", help="versão curta, para subagente")
    s.set_defaults(func=cmd_briefing)

    s = sub.add_parser("index", help="índices gerados")
    s.add_argument("--update", action="store_true")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("new", help="cria decisão, registro do diário ou housekeeping")
    s.add_argument("kind", choices=["decision", "journal", "housekeeping"])
    s.add_argument("title", nargs="?")
    s.add_argument("--author")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("archive", help="tira da memória ativa sem apagar")
    s.add_argument("path")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_archive)

    s = sub.add_parser("init", help="config e esqueleto da memória")
    s.add_argument("--profile", default="")
    s.add_argument("--name", default="", help="nome do projeto")
    s.add_argument("--memory-dir", default="memory", help="pasta da memória")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("profiles", help="perfis de stack")
    s.set_defaults(func=cmd_profiles)

    s = sub.add_parser("hook", help="uso interno do plugin")
    s.add_argument("name")
    s.set_defaults(func=lambda a: _hook(a.name))
    return p


def _hook(name: str) -> int:
    from .hooks import run

    return run(name)


def main(argv: list[str] | None = None) -> int:
    # UTF-8 na saída: no console do Windows, o codepage padrão corrompe os acentos.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    args = _parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
