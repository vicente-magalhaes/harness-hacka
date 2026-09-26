"""Ponto de entrada do plugin: CLI e hooks, sem instalar pacote nenhum.

O bootstrap fica dentro do `try` de propósito. Se o pacote estiver quebrado (um `git pull`
pela metade, um Python antigo), o hook avisa e sai 0 em vez de derrubar a sessão.
"""

import sys
from pathlib import Path

_IN_HOOK = len(sys.argv) > 1 and sys.argv[1] == "hook"

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from harness_hacka.cli import main
except Exception as error:  # noqa: BLE001
    if _IN_HOOK:
        print(f"[harness-hacka] pacote não importável, hook desligado: {error!r}", file=sys.stderr)
        raise SystemExit(0) from None
    raise

raise SystemExit(main())
