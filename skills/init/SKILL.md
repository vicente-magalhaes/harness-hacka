---
name: init
description: Instalar o harness-hacka neste projeto ou migrar uma memória que já existe (pasta de notas, ADRs, diário). Cria a config, o esqueleto da memória e o índice, sem sobrescrever nada.
argument-hint: "[profile: python | nextjs]"
---

# Instalar o harness-hacka

`harness-hacka` é o CLI deste plugin. Se o shell não achar o comando, use
`python "${CLAUDE_PLUGIN_ROOT}/bin/harness-hacka.py"` (ou `python3`). Sem essa variável
(fora do Claude Code), use
`uvx --from git+https://github.com/vicente-magalhaes/harness-hacka harness-hacka`.

O plugin é o mecanismo. `.claude/harness-hacka.json` é a política deste projeto. A pasta de
memória é o conteúdo. Esta skill cria a política e o esqueleto do conteúdo. O que o projeto
já tem vale mais que o modelo: nunca sobrescreva nada em silêncio.

## 1. Levantar o que existe

Não escreva nada ainda. Descubra, com números:

- `AGENTS.md` e `CLAUDE.md`: existem? Tem tabela de "o que ler quando"? Tem seção de regras?
- Agentes: o time usa só Claude Code, ou também Devin (`.devin/`), Codex, Cursor?
- Memória: pastas como `memory/`, `memoria/`, `docs/`, `notes/`, `adr/`, `decisions/`.
  Quantos arquivos, que formato, se têm frontmatter.
- Decisões: ADRs em arquivo, ou uma tabela (D-01, D-02) dentro de uma nota? ADR do
  harness-memoria (`data:`, `substitui:`, `## Regra`) é lido como está: mover para
  `decisions/` com `git mv` basta, sem reescrever decisão aceita.
- Diário: existe? Um arquivo por mês, por sessão?
- Stack: `pyproject.toml` indica `python`; `package.json` com `next` indica `nextjs`. Rode
  `harness-hacka profiles` para ver os disponíveis.
- CI: `.github/workflows/`.
- Hooks próprios em `.claude/settings.json`, principalmente de segredos.

## 2. Plano de migração

Se já existe memória em outro formato, pare e mostre um plano curto antes de escrever.
Migrar histórico é decisão da pessoa. O plano segue estas regras:

- Notas existentes ficam onde estão e ganham frontmatter: `read_when` (obrigatório) e
  `review_by` (sugira uma data). Se o CLAUDE.md já tem a coluna "ler quando", copie de lá.
  Não invente.
- `summary` no frontmatter é o texto da coluna "Conteúdo" do índice. Copie o que já existe.
- Tabela de decisões dentro de uma nota fica como está, como registro histórico. Decisões
  novas vão para `decisions/`, uma por arquivo. Converter o histórico só se a pessoa pedir.
- Índice escrito à mão no CLAUDE.md: troque pela região gerada
  (`<!-- harness-hacka:index -->` e `<!-- /harness-hacka:index -->`) só depois de conferir que
  o gerado tem as mesmas linhas.

## 3. Criar

```bash
harness-hacka init --profile <perfil> --name "<nome do projeto>"
```

Use `--memory-dir <pasta>` se a memória não fica em `memory/`. O comando cria
`.claude/harness-hacka.json`, os READMEs de cada pasta e gera os índices. Não sobrescreve
nada.

Depois, ajuste na config só o que difere do padrão:

- `housekeeping.markers`: textos que marcam conteúdo provisório neste projeto.
- `guard.secrets: false`, se o projeto já tem hook próprio de segredos. Evita bloqueio em
  dobro com mensagens diferentes.
- `triggers`: arquivos que, quando mudam, costumam carregar decisão (além dos do perfil).

## 4. Conferir

```bash
harness-hacka index --update
harness-hacka check
harness-hacka briefing
```

O check precisa sair 0. Aviso (nota vencida) não reprova. O briefing é o que toda sessão
nova vai receber: leia com a pessoa e confirme que faz sentido.

## 5. Ligar para o time

- `.claude/harness-hacka.json` precisa ir para o git: é o gate. Confira que o `.gitignore`
  não o ignora (`git check-ignore .claude/harness-hacka.json` não pode devolver nada).
- No `.claude/settings.json` do projeto, `extraKnownMarketplaces` e `enabledPlugins`. O
  README do harness-hacka tem o trecho pronto.
- Se há CI, um passo com `uvx --from git+https://github.com/<dono>/harness-hacka harness-hacka check`.
- Se o time usa Devin: `harness-hacka init --agent devin`. Cria `.devin/config.json` (o
  plugin) e `.devin/hooks.v1.json` (os hooks pelo repositório), e diz o que falta na nuvem.
- Instrução comum a vários agentes: o conteúdo no `AGENTS.md` e o `CLAUDE.md` com uma linha
  só, `@AGENTS.md`. Symlink não serve no Windows.

## 6. Registrar

Adotar o harness é decisão do time. Proponha com `/harness-hacka:decide`. Quem aceita é a
pessoa.
