"""Leitura de markdown do jeito que a memória precisa: título, seções, itens e links.

Tudo aqui ignora o que está dentro de bloco de código. Sem isso, um exemplo de formato
escrito numa cerca ```markdown vira seção de verdade e engana quem lê.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
# Destino com parênteses equilibrados, como o CommonMark aceita: o route group do Next.js
# (`app/(backend)/`) é caminho real, e cortar no primeiro `)` acusaria link quebrado.
_LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+\"[^\"]*\")?\)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_ITEM = re.compile(r"^\s{0,1}[-*]\s+(.*)$")


def fence_mask(lines: list[str]) -> list[bool]:
    """`True` para cada linha que está dentro de um bloco de código (inclusive as cercas)."""
    inside: list[bool] = []
    opening: str | None = None
    for line in lines:
        match = _FENCE.match(line)
        if opening is None:
            if match:
                opening = match.group(1)
                inside.append(True)
            else:
                inside.append(False)
        else:
            inside.append(True)
            if match and match.group(1)[0] == opening[0] and len(match.group(1)) >= len(opening):
                opening = None
    if opening is not None:
        # Cerca aberta e nunca fechada: perder o arquivo inteiro é pior que o defeito que a
        # máscara corrige. Trata como se não houvesse cerca nenhuma.
        return [False] * len(lines)
    return inside


def with_mask(lines: list[str]) -> list[tuple[str, bool]]:
    return list(zip(lines, fence_mask(lines), strict=True))


def title(body: str) -> str:
    for line, inside in with_mask(body.splitlines()):
        if not inside and line.startswith("# "):
            return line[2:].strip()
    return ""


def sections(body: str, level: int = 2) -> dict[str, list[str]]:
    """Mapeia o título de cada seção `##` para as linhas dela (sem o título)."""
    mark = "#" * level + " "
    above = re.compile(rf"^#{{1,{level}}} ")
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line, inside in with_mask(body.splitlines()):
        if not inside and line.startswith(mark):
            current = line[len(mark) :].strip()
            result.setdefault(current, [])
            continue
        if not inside and above.match(line):
            current = None
            continue
        if current is not None:
            result[current].append(line)
    return result


def section(body: str, name: str) -> list[str] | None:
    """Linhas da seção cujo título começa com `name` (sem diferenciar maiúsculas)."""
    target = name.casefold()
    for section_title, lines in sections(body).items():
        if section_title.casefold().startswith(target):
            return lines
    return None


def list_items(lines: list[str] | None) -> list[str]:
    """Itens de lista de primeiro nível. Continuação recuada entra no item de cima."""
    if not lines:
        return []
    result: list[str] = []
    for line, inside in with_mask(lines):
        if inside:
            continue
        match = _ITEM.match(line)
        if match:
            result.append(match.group(1).strip())
        elif result and line.startswith(("  ", "\t")) and line.strip():
            result[-1] = f"{result[-1]} {line.strip()}"
    return result


def relative_links(body: str) -> list[tuple[int, str]]:
    """(número da linha, destino) de cada link relativo, fora de código."""
    found: list[tuple[int, str]] = []
    for number, (line, inside) in enumerate(with_mask(body.splitlines()), start=1):
        if inside:
            continue
        for match in _LINK.finditer(_INLINE_CODE.sub("", line)):
            target = match.group(1).strip("<>")
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("#"):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if target:
                found.append((number, target))
    return found


def lines_outside_code(body: str) -> list[tuple[int, str]]:
    return [
        (number, _INLINE_CODE.sub("", line))
        for number, (line, inside) in enumerate(with_mask(body.splitlines()), start=1)
        if not inside
    ]
