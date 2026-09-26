# harness-hacka

Memória de projeto para agentes de código. O agente propõe; quem decide é uma pessoa.

[![CI](https://github.com/vicente-magalhaes/harness-hacka/actions/workflows/ci.yml/badge.svg)](https://github.com/vicente-magalhaes/harness-hacka/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

O agente esquece tudo entre uma sessão e outra. O `CLAUDE.md` resolve isso até começar a
mentir: a nota que dizia "fila no Postgres" continua lá depois que o time trocou para Redis,
e o agente segue a nota. O harness-hacka guarda a memória no próprio repositório, tira do
caminho o que envelheceu e não deixa o agente tratar uma proposta como decisão tomada.

```text
→ memória em markdown, no repositório, revisada junto com o código
→ o que envelhece sai do caminho, não do histórico
→ o agente propõe, uma pessoa aceita, e isso é hook, não pedido
→ o núcleo é igual em todo projeto; o que muda por stack é um perfil
→ sem banco, sem serviço, sem dependência
```

## Veja funcionando

```text
(início da sessão: o harness injeta um resumo da memória)
  Housekeeping pendente: 2 notas vencidas, 1 registro do diário para triagem.
  2 commits desde o último registro do diário.

Você: /harness-hacka:decide frete pela API dos Correios
IA:   A 0003 trata da fila de pedidos, não de frete. Nenhuma decisão viva cobre isso.
      Qual é a alternativa que vocês consideraram?
      ...
      Criei memory/decisions/0004-frete-pela-api-dos-correios.md, status proposed.
      Para aceitar, responda `accept 0004`.

Você: pode marcar como aceita
IA:   O guard negou a edição: "Aceitar a decisão 0004 é ato de uma pessoa, e o harness-hacka
      não deixa o agente fazer isso sozinho." Responda `accept 0004` e eu refaço.

Você: accept 0004
IA:   Feito: 0004 accepted, decided_by: Ana Souza.

Você: /harness-hacka:housekeeping
IA:   3 candidatos. Laudo do inspector:
      1. memory/pedidos.md → update. Cita a 0002 (fila no Postgres), superseded pela 0003.
         Evidência: pedidos.md:8.
      2. memory/journal/2026-09-18-1030-teste-de-carga-da-fila.md → promote a lição para
         lessons.md e archive.
      3. memory/deploy.md → ask: o deploy ainda é manual?
      Quais aplico?

Você: 1 e 2
IA:   Aplicado. Registro em memory/archive/housekeeping/2026-09-26-1812.md.
```

<details>
<summary><strong>O que o agente recebe no início da sessão</strong></summary>

Trecho da saída de `harness-hacka briefing` no projeto de exemplo, com a 0004 ainda proposta
(dados fictícios; só as quebras de linha foram mudadas para caber aqui):

```markdown
### Pendências
- A decisão 0004 está proposed. Só uma pessoa aceita: mostre o resumo e peça que ela
  responda `accept 0004`.
- Housekeeping pendente: 2 notas vencidas, 1 registro do diário para triagem, 1 marcador
  de provisório. No começo da conversa, ofereça uma vez `/harness-hacka:housekeeping`, sem
  insistir.
- 2 commits desde o último registro do diário. Ao fechar o trabalho, ofereça
  `/harness-hacka:journal`.

### Decisões
- 0001 FastAPI no back-end (accepted, Ana Souza). Regra: Toda rota da API fica sob `/api`,
  em FastAPI.
- 0003 Fila de pedidos no Redis (accepted, Bruno Lima). Regra: Pedido entra no Redis
  Streams; o Postgres guarda só o estado final.
- 0004 Frete pela API dos Correios (proposed: ainda não vale).
- (+1 superseded, deprecated ou rejected: não siga, veja o substituto)

### Última sessão
2026-09-26 16:40 · Ana Souza · partial · Tela de checkout com frete
(`memory/journal/2026-09-26-1640-tela-de-checkout.md`)
Next steps:
- [ ] Decidir a 0004 (frete pelos Correios) com o Bruno
- [ ] Trocar a tabela fixa pela chamada real

### Não repetir
- Calcular frete no front → a tabela de regiões vazava inteira no bundle.
  **Lesson:** regra de preço fica no back-end
- Fila no Postgres com SELECT FOR UPDATE → travou acima de 150 pedidos por minuto.
  **Lesson:** fila de alto volume não vai no banco relacional
```

O bloco tem teto (6.000 caracteres por padrão). Quando não cabe, o índice de notas sai
primeiro e as lições mais antigas depois, e cada corte diz o que ficou de fora e onde está.

</details>

## Instalação

Precisa de Claude Code, git e Python 3.10 ou mais novo no PATH. Nada para instalar com pip.

```text
/plugin marketplace add vicente-magalhaes/harness-hacka
/plugin install harness-hacka@harness-hacka
/harness-hacka:init
```

O `/harness-hacka:init` olha o que o projeto já tem (CLAUDE.md, pasta de notas, ADRs,
diário) e propõe um plano antes de escrever qualquer coisa. Não sobrescreve nada.

Para o time inteiro receber o convite ao abrir o projeto, no `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "harness-hacka": { "source": { "source": "github", "repo": "vicente-magalhaes/harness-hacka" } }
  },
  "enabledPlugins": { "harness-hacka@harness-hacka": true }
}
```

No CI, a auditoria roda sem instalar o plugin:

```yaml
- run: uvx --from git+https://github.com/vicente-magalhaes/harness-hacka harness-hacka check
```

## Na prática

Um dia de trabalho com o harness ligado:

1. **Abrir a sessão.** Nada para rodar. O hook de início injeta o resumo: decisões que
   valem, o próximo passo da última sessão, o que não repetir e o que está pendente. O
   agente começa sabendo o que a sessão de ontem aprendeu.
2. **Trabalhar.** O guard fica de fundo. Leitura de `.env` ou chave é negada. Chave colada
   numa nota é negada. `rm` na memória é negado. Quando uma edição toca um arquivo que
   costuma carregar decisão (`pyproject.toml`, migração, compose), o agente sugere
   `/harness-hacka:decide` uma vez.
3. **Decidir.** `/harness-hacka:decide` pergunta o gatilho, as opções e por que cada uma foi
   descartada, e escreve a decisão como `proposed`. Ela só vira `accepted` quando você
   escreve `accept NNNN` no chat.
4. **Fechar a sessão.** `/harness-hacka:journal` escreve o registro: o que mudou, os dead
   ends, a verificação com número e os next steps. É o que a próxima sessão vai receber.
5. **De tempos em tempos.** Quando o resumo avisa que há housekeeping pendente,
   `/harness-hacka:housekeeping`. O inspector propõe, com evidência, o que manter,
   atualizar, promover ou arquivar. Você escolhe os itens, e fica o registro de quem aprovou.
6. **No CI.** `harness-hacka check` reprova memória que mente: link quebrado, índice
   defasado, decisão substituída ainda citada, chave na memória.

## Como a memória fica

```text
memory/
├── README.md     índice gerado a partir dos arquivos
├── *.md          notas: o que vale hoje; cada uma diz quando ler e quando revisar
├── lessons.md    o que não repetir (qualquer nota com type: lessons)
├── decisions/    por que é assim: proposed → accepted → superseded
├── journal/      o que aconteceu, um arquivo por sessão
└── archive/      o que já não vale; nada é apagado
```

O journal é rascunho. O housekeeping decide o que dura:

```text
sessão ──► journal ──► housekeeping ──┬──► nota        fato que continua valendo
                                      ├──► decisão     escolha, com as opções descartadas
                                      ├──► lesson      o que não repetir
                                      └──► archive/    o resto, fora do contexto do agente
```

Um arquivo por registro, e não um por mês, porque o time junta tudo na mesma branch. Dois
registros no fim do mesmo arquivo viram conflito de merge.

Uma nota é markdown com duas ou três linhas de frontmatter:

```markdown
---
read_when: antes de mexer em pedidos ou na fila
review_by: 2026-10-30
---
# Pedidos
```

`read_when` monta o índice. `review_by` diz quando a nota vence. Sem ela, a nota vence
depois de 30 dias sem commit.

Os status de decisão seguem o [MADR](https://adr.github.io/madr/): `proposed`, `accepted`,
`rejected`, `deprecated` e `superseded`. Memória que já existe em português (`aceita`,
`proposta`, `substituída`) é lida sem conversão.

## O que roda sozinho

| Hook | Quando | O que faz |
|---|---|---|
| `SessionStart` | início, retomada, `/clear` e depois de compactar | injeta o resumo: pendências, decisões vivas, último next step, o que não repetir |
| `SubagentStart` | todo subagente | versão curta: decisões e o que não repetir |
| `UserPromptSubmit` | cada mensagem sua | se você escreveu `accept NNNN`, registra a aprovação por 30 minutos nesta sessão |
| `PreToolUse` | antes de ler, escrever ou rodar comando | o guard: nega segredo, chave gravada na memória, `rm` na memória e status de decisão sem aprovação |
| `PostToolUse` | depois de editar | se o arquivo costuma carregar decisão, sugere `/harness-hacka:decide` uma vez por sessão |

Sem `.claude/harness-hacka.json` no projeto, nenhum hook faz nada. Dá para deixar o plugin
ligado no nível do usuário sem que ele apareça em projeto que não pediu.

## Comandos

| Skill | Para quê |
|---|---|
| `/harness-hacka:init` | instalar no projeto, ou migrar uma memória que já existe |
| `/harness-hacka:journal` | fechar a sessão: o que mudou, os dead ends, os next steps |
| `/harness-hacka:decide` | escrever uma decisão com as opções descartadas e o porquê |
| `/harness-hacka:housekeeping` | o subagente `inspector` propõe keep, update, promote, merge, archive ou ask; você escolhe |

A parte que não precisa de LLM é um CLI. As skills chamam ele, e o CI também:

```text
harness-hacka status      estado da memória e candidatos do housekeeping (--json para as skills)
harness-hacka check       auditoria; sai 1 se houver erro (--strict: aviso também reprova)
harness-hacka briefing    o bloco que o início de sessão injeta (--subagent: a versão curta)
harness-hacka index       índices gerados a partir dos arquivos (--update)
harness-hacka new         decision, journal ou housekeeping, a partir dos modelos
harness-hacka archive     tira da memória ativa sem apagar, com git mv e o motivo
harness-hacka init        config e esqueleto da memória (--profile, --memory-dir)
```

Saída real no projeto de exemplo:

```text
$ harness-hacka status
harness-hacka · Loja Exemplo · memória em memory/

  notas              3 (2 vencidas)
  decisões           4 (2 accepted, 1 proposed, 1 superseded)
  diário             2 registros ativos
  arquivo            0 itens
  último housekeeping nunca
  2 commits desde o último registro

Para o housekeeping (3):
  - memory/deploy.md: sem alteração há 56 dias (limite de 30)
  - memory/pedidos.md: venceu em 2026-09-20 (`review_by`); 1x 'provisório'
  - memory/journal/2026-09-18-1030-teste-de-carga-da-fila.md: registro de 8 dias: promova o que vale e arquive o resto

Erros (1), rode `harness-hacka check`:
  x memory/pedidos.md:8  cita a decisão 0002, que foi substituída por 0003. Aponte para a que vale  [dead-reference]
```

O que o `check` reprova: `broken-link`, `outdated-index`, `missing-read-when`,
`dead-reference` (citação de decisão substituída), `supersession` (declarada de um lado
só), `decision-owner` (accepted sem `decided_by`), `entry-sections`, `unfilled-template` e
`secret` (padrão de chave ou token em qualquer arquivo da memória). `stale` e
`journal-triage` são avisos: viram candidatos do housekeeping.

## Decisão humana, de verdade

Escrever no `CLAUDE.md` "não aceite decisões sozinho" funciona até o agente esquecer. No
harness-hacka, a regra está num hook:

1. O agente escreve a decisão como `proposed`.
2. O guard nega qualquer edição que ponha `status: accepted`, ou que tire de `accepted`. O
   `deny` vale em qualquer modo de permissão, inclusive com edições auto-aprovadas.
3. A liberação vem do texto que você envia no chat, `accept 0004` (também vale `approve`,
   `aceito` ou `aprovo`). O hook `UserPromptSubmit` lê a sua mensagem, nunca o que o agente
   escreve. A frase exige o número: "pode aceitar" não libera, para a aprovação dizer
   exatamente o que foi aprovado. `do not accept 0004` e `não aceito 0004` também não.
4. A decisão aceita guarda `decided_by`, e o `check` reprova `accepted` sem dono.

Por que não `ask`: o pedido de confirmação segue o modo da sessão e, em modo automático,
pode passar sem ninguém ver.

## Perfis de stack

O núcleo não sabe qual é a stack. O perfil diz quais arquivos costumam carregar decisão e o
que conta como verificação no journal.

| Perfil | Triggers | Verify |
|---|---|---|
| `python` | `pyproject.toml`, `Dockerfile*`, `docker-compose*.yml`, migrações, CI | `uv run pytest`, `uv run ruff check .` |
| `nextjs` | `package.json`, `next.config.*`, `middleware.ts`, `prisma/schema.prisma`, CI | `npm run lint`, `npx tsc --noEmit`, `npm test` |

Outra stack é um JSON de dez linhas em [`src/harness_hacka/profiles/`](src/harness_hacka/profiles/).
Copie um existente e troque os triggers.

## Configuração

`.claude/harness-hacka.json`. A presença do arquivo liga o harness no projeto. Todo campo tem
padrão; escreva só o que difere.

```json
{
  "project": "Loja Exemplo",
  "profile": "python",
  "memory_dir": "memoria",
  "housekeeping": { "stale_after_days": 14, "markers": ["(sugestão Claude)", "[HIPÓTESE]"] },
  "guard": { "secrets": false },
  "triggers": { "supabase/migrations/**": "estrutura do banco", "Dockerfile*": null }
}
```

| Campo | Padrão | Para quê |
|---|---|---|
| `memory_dir` | `"memory"` | pasta da memória |
| `profile` | `""` | `python`, `nextjs` ou nenhum |
| `index.files` | `["CLAUDE.md"]` | onde procurar regiões de índice gerado, além dos READMEs da memória |
| `housekeeping.stale_after_days` | `30` | nota sem `review_by` vence depois disso sem commit |
| `housekeeping.journal_after_days` | `7` | registro mais velho que isso entra na triagem |
| `housekeeping.proposal_after_days` | `3` | proposta parada vira lembrete |
| `housekeeping.markers` | do perfil | textos que marcam provisório; o inspector confere se ainda valem |
| `briefing.max_chars` | `6000` | tamanho máximo do resumo do início de sessão |
| `guard.secrets` | `true` | nega ler e escrever `.env`, chaves e credenciais; desligue se o projeto já tem hook próprio |
| `guard.memory_secrets` | `true` | nega gravar chave ou token na memória |
| `guard.human_decisions` | `true` | a aprovação de decisão descrita acima |
| `triggers` | do perfil | glob → motivo; `null` desliga um trigger herdado |
| `verify` | do perfil | comandos citados como evidência no journal |

Chave desconhecida ou tipo errado reprova: config que o harness não entende é config que
mente sobre o que está ligado.

## Como se compara

**Só `CLAUDE.md` e uma pasta de notas.** É onde quase todo projeto começa, e o harness
aproveita: as notas continuam onde estão e ganham duas ou três linhas de frontmatter. O que
muda é que o índice passa a ser gerado, o que envelhece é detectado e a decisão ganha dono.

**[harness-memoria](https://github.com/cassoli-filipe/harness-memoria)**, de Filipe
Cassoli. É de lá que vêm as ideias centrais: o gate por arquivo de config, a separação entre
mecanismo, política e conteúdo, a seção de dead ends, o briefing com teto e o princípio de
que ponteiro velho é pior que ponteiro nenhum. O harness-hacka muda três coisas. Um registro
por sessão em vez de um arquivo por mês, para times que juntam na mesma branch. Um
housekeeping com subagente, em vez de só auditoria. E aprovação humana garantida por hook.
O harness-memoria vai mais fundo em reafirmação de regras dentro da sessão e em auditoria de
ADR.

**[OpenSpec](https://github.com/Fission-AI/OpenSpec)**. Complementar. O OpenSpec cuida do
que vai ser construído: specs e propostas de mudança. O harness-hacka cuida do que o projeto
já sabe. A ideia de que arquivar devolve o trabalho para a fonte da verdade veio de lá. Dá
para usar os dois no mesmo repositório.

## Limites conhecidos

- Os hooks são do Claude Code. A memória é markdown puro e outros agentes (Copilot, Codex,
  Cursor) leem os mesmos arquivos, mas sem briefing e sem guard.
- O guard cobre as ferramentas de edição e os comandos de shell mais comuns. Um script que
  edita a decisão por outro caminho escapa. O `check` pega `accepted` sem `decided_by`.
- Os padrões de segredo são de alta precisão, não de alta cobertura. Não substituem um
  scanner de segredos no CI.
- A idade da nota vem do último commit. Nota editada e ainda não commitada conta pela data
  antiga.
- O housekeeping depende do julgamento do inspector. Por isso toda ação vem com evidência e
  passa por você.
- Os hooks chamam `python` e, se não houver, `python3`, por um shell POSIX. No Windows isso
  quer dizer Git Bash, que o Claude Code já usa.

## Desenvolvimento

```bash
uv sync
uv run pytest                          # o CI roda em Windows e Linux
uv run ruff check .
python bin/harness-hacka.py check       # o harness audita a própria memória
claude plugin validate .
claude --plugin-dir <pasta do harness>   # a partir de um projeto com .claude/harness-hacka.json
```

Zero dependências em runtime é requisito: os hooks rodam com o `python` do PATH, fora do venv
do projeto. Este repositório usa o próprio harness; a memória dele está em
[`memory/`](memory/README.md).

## Licença

MIT
