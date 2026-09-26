"""O estado da memória num lugar só: é o que `harness-hacka status` mostra e o inspector usa."""

from __future__ import annotations

from datetime import date, datetime

from . import git
from .checks import Finding, audit, stale_reason
from .memory import Memory, count_markers, date_from_name, plural


def build(memory: Memory, today: date, now: datetime) -> dict[str, object]:
    cfg = memory.cfg
    changed = git.last_changed(cfg.root, cfg.memory.relative_to(cfg.root))
    findings = audit(memory, today, changed)
    candidates: list[dict[str, object]] = []

    notes = []
    for note in memory.notes:
        when = changed.get(note.rel)
        markers = count_markers(note.body, cfg.markers)
        stale = stale_reason(note.review_by, note.rel, changed, today, cfg.stale_after_days)
        notes.append(
            {
                "path": note.rel,
                "title": note.title,
                "read_when": note.read_when,
                "review_by": note.review_by.isoformat() if note.review_by else None,
                "changed_on": when.isoformat() if when else None,
                "markers": markers,
                "stale": bool(stale),
            }
        )
        if stale:
            reasons = [stale, *(f"{n}x '{m}'" for m, n in markers.items())]
            candidates.append({"path": note.rel, "kind": "note", "reasons": reasons})

    decisions = []
    for d in sorted(memory.decisions, key=lambda d: d.number):
        decisions.append(
            {
                "number": d.number,
                "title": d.title,
                "status": d.status,
                "date": d.decision_date.isoformat() if d.decision_date else None,
                "decided_by": d.decided_by or None,
                "supersedes": d.supersedes,
                "superseded_by": d.superseded_by,
                "path": d.rel,
            }
        )
    for f in findings:
        if f.code == "proposal-waiting":
            candidates.append({"path": f.file, "kind": "decision", "reasons": [f.message]})

    entries = []
    for e in sorted(memory.entries, key=lambda e: e.moment or datetime.min):
        entries.append(
            {
                "path": e.rel,
                "moment": e.moment.isoformat(timespec="minutes") if e.moment else None,
                "title": e.title,
                "author": e.author or None,
                "status": e.status or None,
                "dead_ends": len(e.dead_ends),
            }
        )
    for f in findings:
        if f.code == "journal-triage":
            candidates.append({"path": f.file, "kind": "entry", "reasons": [f.message]})

    runs = sorted(d for d in (date_from_name(p) for p in memory.housekeeping_runs) if d)
    last = memory.last_entry
    commits = git.commits_since(cfg.root, last.moment if last else None)

    return {
        "project": cfg.project,
        "memory_dir": cfg.memory_dir,
        "profile": cfg.profile or None,
        "today": today.isoformat(),
        "notes": notes,
        "decisions": decisions,
        "journal": entries,
        "archived": len(memory.archived),
        "housekeeping": {
            "last_run": runs[-1].isoformat() if runs else None,
            "candidates": candidates,
        },
        "commits_since_last_entry": len(commits) if last else None,
        "findings": [f.as_dict() for f in findings],
        "errors": sum(1 for f in findings if f.level == "error"),
        "warnings": sum(1 for f in findings if f.level == "warning"),
    }


def render(p: dict[str, object]) -> str:
    notes = p["notes"]
    decisions = p["decisions"]
    entries = p["journal"]
    housekeeping = p["housekeeping"]
    assert isinstance(notes, list) and isinstance(decisions, list)
    assert isinstance(entries, list) and isinstance(housekeeping, dict)

    by_status: dict[str, int] = {}
    for d in decisions:
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    decisions_summary = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) or "nenhuma"
    stale = sum(1 for n in notes if n["stale"])
    archived = int(p["archived"])  # type: ignore[call-overload]

    lines = [
        f"harness-hacka · {p['project']} · memória em {p['memory_dir']}/",
        "",
        f"  notas              {len(notes)}"
        + (f" ({plural(stale, 'vencida', 'vencidas')})" if stale else ""),
        f"  decisões           {len(decisions)} ({decisions_summary})",
        f"  diário             {plural(len(entries), 'registro ativo', 'registros ativos')}",
        f"  arquivo            {plural(archived, 'item', 'itens')}",
        f"  último housekeeping {housekeeping['last_run'] or 'nunca'}",
    ]
    commits = p["commits_since_last_entry"]
    if commits:
        lines.append(f"  {plural(int(commits), 'commit', 'commits')} desde o último registro")  # type: ignore[call-overload]

    candidates = housekeeping["candidates"]
    assert isinstance(candidates, list)
    if candidates:
        lines += ["", f"Para o housekeeping ({len(candidates)}):"]
        for c in candidates:
            lines.append(f"  - {c['path']}: {'; '.join(c['reasons'])}")

    errors = [f for f in p["findings"] if f["level"] == "error"]  # type: ignore[union-attr]
    if errors:
        lines += ["", f"Erros ({len(errors)}), rode `harness-hacka check`:"]
        for f in errors[:8]:
            lines.append("  " + Finding(**f).format())  # type: ignore[arg-type]
        if len(errors) > 8:
            lines.append(f"  ... e mais {len(errors) - 8}")
    return "\n".join(lines)
