# Diário

Um arquivo por sessão: `AAAA-MM-DD-HHMM-titulo.md`. Crie com `/harness-hacka:journal`.

Um arquivo por registro, e não um por mês, porque o time junta tudo na mesma branch: dois
registros no fim do mesmo arquivo viram conflito de merge.

O diário é memória de curto prazo. No housekeeping, o que dura é promovido (vira nota,
decisão ou lição em `lessons.md`) e o registro vai para `archive/`.

## Formato

Frontmatter com `author`, `status` (`done`, `partial`, `blocked`) e `decisions`. Seções
obrigatórias: `## Changes`, `## Dead ends`, `## Verification` e `## Next steps`.

Dead end, um por linha:

```
- {abordagem} → falhou porque {razão}. **Lesson:** {lição em imperativo}
```

A lição vai no fim porque é a parte que o início de sessão precisa entregar inteira.
