# Memória do projeto

O que o projeto sabe, escrito para pessoas e para agentes de código. Mantida com o
harness-hacka.

| Onde | O que guarda | Quem escreve |
|---|---|---|
| `*.md` (aqui) | Notas: o que vale hoje. Cada uma diz quando ler (`read_when`) e quando revisar (`review_by`). | Qualquer pessoa, a qualquer momento |
| `lessons.md` | O que não repetir. Qualquer nota com `type: lessons`. | O housekeeping promove para cá |
| `decisions/` | Por que é assim. Uma decisão por arquivo. Só uma pessoa aceita. | `/harness-hacka:decide` |
| `journal/` | O que aconteceu em cada sessão, inclusive o que não funcionou. | `/harness-hacka:journal` |
| `archive/` | O que já não vale. Nada é apagado. | `/harness-hacka:housekeeping` |

## Notas

<!-- harness-hacka:index -->
| Arquivo | Conteúdo | Ler quando |
|---|---|---|
| [lessons.md](lessons.md) | O que já foi tentado e não funcionou, com a lição | antes de mexer em hook, no briefing, no guard ou no formato do journal |
<!-- /harness-hacka:index -->

## Regras

1. Toda nota começa com frontmatter: `read_when` (obrigatório) e `review_by` (recomendado).
2. Decisão `accepted` não se reescreve. Mudou de ideia: nova decisão que substitui a antiga.
3. Registro do diário é curto (até ~25 linhas) e honesto em `## Dead ends`.
4. Sem segredo, token ou dado pessoal. O harness bloqueia na escrita e a auditoria reprova.
5. Não apague. O housekeeping move para `archive/`, com data e motivo.
