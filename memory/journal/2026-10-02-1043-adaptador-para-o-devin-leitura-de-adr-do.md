---
author: Vicente
status: partial
decisions: [0002]
---

# Adaptador para o Devin, leitura de ADR do harness-memoria e trava de hooks do git

## Changes

- `agents.py`: traduz o evento do Devin (`read`, `edit`, `exec`, `apply_patch`, chaves de
  caminho) e devolve o bloqueio como `decision: block` com saída 2. Proposta 0002.
- Guard lê patch; nega `--no-verify`, `commit -n`, `HUSKY=0`, `core.hooksPath` (`guard.git_hooks`)
  e `git add --force` (sob `guard.secrets`).
- `init --agent devin` gera `.devin/config.json` e `.devin/hooks.v1.json`; `events` mostra os
  hooks que rodaram, só com nomes de chave. Resumo do início deduplicado no Devin.
- Lê ADR do harness-memoria como está (`data`, `substitui`, `substituido-por`, `## Regra`).
- `index.files` passa a incluir `AGENTS.md`; perfil `nextjs` casa `**/prisma/schema.prisma`;
  link com parênteses (route group do Next.js) não acusa mais quebrado. Versão 0.2.0.

## Why

A Poli Bridge vai usar o Devin e migrar do harness-memoria; o guard deixava passar tudo que
viesse do Devin, e o perfil `nextjs` não via o schema dentro de `web/`.

## Dead ends

- Trocar a regex do `_LINK` por script Python em heredoc → o `\[` virou escape inválido e o
  `assert` barrou sem gravar nada. **Lesson:** regex com barra invertida se troca pela
  ferramenta de edição, não por string Python dentro de heredoc.

## Verification

- `uv run pytest`: 162 passando (eram 114). `ruff check` e `ruff format --check` limpos.
- `python bin/harness-hacka.py check`: 0 erros, 1 aviso (0001 proposta). Passo novo do CI
  simulado no Git Bash: saída 2 e `decision: block`.
- Contra a Poli Bridge: `check` com 0 erros sobre os ADRs reais do harness-memoria.

## Next steps

- [ ] Aceitar ou recusar a 0002 e a 0001.
- [ ] Push e tag `v0.2.0`; o CI da Poli Bridge instala o harness daqui.
- [ ] Rodar uma sessão do Devin e conferir em `harness-hacka events` as chaves reais das
  ferramentas de arquivo.
