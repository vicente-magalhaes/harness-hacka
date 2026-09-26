---
status: proposed
date: 2026-09-26
decided_by:
supersedes: []
superseded_by: []
---

# 0001: Harness próprio, em repositório separado, distribuído como plugin

## Rule

- O harness-hacka vive neste repositório e chega aos projetos como plugin do Claude Code.
  Projeto nenhum copia o código dele: instala o plugin e escreve só a própria config.

## Context

Um time de quatro pessoas usava Claude Code com uma memória básica: notas numeradas numa
pasta e uma tabela "ler quando" no CLAUDE.md. Faltavam quatro coisas: registro do que cada
sessão aprendeu, decisões com trilha, limpeza do que envelhece e garantia de que decisão é
de uma pessoa. O harness-memoria (Filipe Cassoli) resolve boa parte para um dev só, mas não
declara licença e usa um arquivo de diário por mês, que vira conflito de merge quando quatro
pessoas juntam na mesma branch.

A ideia é que o harness seja reaproveitado por outros times, inclusive com outra stack.

## Options

### Repositório próprio, como plugin e marketplace (escolhida)

O repositório é plugin e marketplace ao mesmo tempo (`source: "./"`). O projeto liga com
`extraKnownMarketplaces` e `enabledPlugins` no `.claude/settings.json`, e cada pessoa do
time recebe o convite ao confiar na pasta. Adaptar para outra stack é escrever um perfil.

### Pasta dentro do repositório do produto

Descartada porque produto e ferramenta têm ciclos de vida diferentes, e outro time teria de
copiar a pasta para usar. Duas cópias divergem na primeira correção.

### Usar o harness-memoria como está

Descartada porque não declara licença, o diário mensal gera conflito com várias pessoas na
mesma branch, e não há housekeeping com agente nem aprovação humana garantida por hook.

### Só CLAUDE.md e a pasta de notas, como antes

Descartada porque nada detecta o que envelheceu, e nada impede o agente de tratar uma
proposta como decisão tomada.

## Consequences

Boas: um lugar só para corrigir; o mesmo harness serve a qualquer projeto que tenha a
config; o próprio harness é auditado pelo harness.

Ruins, e aceitas: enquanto o repositório não estiver no GitHub, o time só testa com
`claude --plugin-dir`. Mudança no harness só chega ao time depois de commit e
`/plugin update`.

## Revisit when

Se um segundo time precisar de uma regra que não cabe em config nem em perfil, ou se o
Claude Code passar a oferecer memória de projeto com decisão humana garantida.
