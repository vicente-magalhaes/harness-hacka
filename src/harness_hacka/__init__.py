"""harness-hacka: memória de projeto para agentes de código.

Três camadas, ideia herdada do harness-memoria de Filipe Cassoli:

- mecanismo: este pacote e o plugin, iguais para todo projeto;
- política: `.claude/harness-hacka.json` do projeto, o que muda por projeto e por stack;
- conteúdo: a pasta de memória do projeto (notas, decisões, diário e arquivo).

Só biblioteca padrão. Os hooks rodam com o `python` do PATH, fora de qualquer venv, e uma
dependência de terceiro transformaria "instalar o plugin" em "gerenciar um ambiente".
"""

__version__ = "0.2.0"
