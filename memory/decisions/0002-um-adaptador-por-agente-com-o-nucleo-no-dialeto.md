---
status: proposed
date: 2026-10-02
decided_by:
supersedes: []
superseded_by: []
---

# 0002: Um adaptador por agente, com o núcleo no dialeto do Claude Code

## Rule

- Agente novo entra por `src/harness_hacka/agents.py`: traduz o evento na entrada e a resposta
  na saída. Guard, aprovação, briefing e gatilhos não ganham `if` por agente.
- O plugin é um só para todo agente. O Devin instala o mesmo `.claude-plugin/plugin.json`.

## Context

A Poli Bridge vai usar o Devin junto com o Claude Code, e as regras do harness precisam valer
para os dois. Medido na documentação do Devin (docs.devin.ai, outubro de 2026): o Devin lê
hooks no formato do Claude, inclusive o `hooks/hooks.json` de plugin do Claude, mas manda as
ferramentas em minúsculas (`read`, `edit`, `exec`, `apply_patch`), bloqueia por
`{"decision": "block"}` ou saída 2, e não documenta `permissionDecision`. O guard comparava
`tool in ("Write", "Edit")`: com o Devin, deixaria tudo passar sem avisar.

Hooks de plugin, o Devin só roda no CLI e no Desktop, e chama de "best effort". Se a nuvem
roda os hooks do repositório (`.devin/hooks.v1.json`), a documentação não diz.

## Options

### Adaptador nas duas pontas, núcleo no dialeto do Claude (escolhida)

`agents.normalize` traduz ferramenta e chaves do evento; `agents.render` devolve o bloqueio no
formato do agente (para o Devin, JSON `decision: block` e saída 2 com o motivo no stderr). O
agente é detectado por `DEVIN_PROJECT_DIR`. `init --agent devin` gera `.devin/config.json` (o
plugin) e `.devin/hooks.v1.json` (os hooks pelo repositório, para a nuvem). Patch, que o Claude
não tem, vira o canônico `ApplyPatch`, e o guard lê as linhas que entram e saem.

### Um plugin por agente

Descartada porque o Devin já instala o plugin do Claude como está. Dois plugins divergem na
primeira correção, o mesmo motivo que a 0001 deu para não copiar o harness por projeto.

### Só AGENTS.md e skills no Devin, sem hook

Descartada porque é o estado que o harness existe para corrigir: regra que depende de o
agente lembrar. Fica como o comportamento onde hook não roda, não como o desenho.

### Núcleo neutro, sem dialeto de nenhum agente

Descartada por ora porque reescreve guard e testes que já valem no Claude Code para ganhar
nada com dois agentes. Se entrar um terceiro agente com formato muito diferente, revisitar.

## Consequences

Boas: o mesmo plugin, as mesmas skills e o mesmo guard no Claude Code e no Devin. A Poli
Bridge passa a ter guard no Devin CLI. `harness-hacka events` mostra quais hooks rodaram, de
qual agente e com quais chaves, sem guardar valor nenhum.

Ruins, e aceitas: as chaves das ferramentas de arquivo do Devin não são documentadas, e o
adaptador aceita as grafias comuns até o `events` mostrar as reais. No Devin CLI com plugin e
`.devin/hooks.v1.json`, cada hook roda duas vezes; o resumo do início é deduplicado, o guard
repete sem efeito. Na nuvem, o guard depende de o Devin rodar hook de repositório, o que
ainda não foi medido.

## Revisit when

Se o `harness-hacka events` de uma sessão do Devin mostrar chaves que o adaptador não lê; se
o Devin passar a rodar hook de plugin na nuvem (aí o `.devin/hooks.v1.json` sobra); ou se um
terceiro agente entrar com um formato de hook que não cabe numa tabela de tradução.
