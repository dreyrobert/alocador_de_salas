# Guia de testes basicos

Esta suite registra um baseline do comportamento atual do projeto antes das
adaptacoes da matheuristica LNS fix-and-optimize.

## Preparar ambiente com uv

```bash
uv sync
```

O `uv sync` usa o `pyproject.toml` e o `uv.lock` para criar/sincronizar o
`.venv` automaticamente.

## Rodar testes

Forma recomendada:

```bash
uv run python -m unittest discover -s tests -v
```

Tambem e possivel ativar o ambiente e rodar os comandos diretamente:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Se voce rodar com `python3` global, fora do `.venv`, alguns testes podem ser
marcados como `skipped` quando dependencias como `pandas` nao estiverem
instaladas nesse Python global.

## O que este baseline cobre

- Conversao de horarios para o formato usado na planilha de saida.
- Regras basicas de abreviacao e formatacao de disciplinas.
- Comportamento de disciplinas agrupadas.
- Extracao basica de salas a partir de CSV.
- Estrutura e simetria da matriz de distancia.
- Deteccao de conflitos de sala, dia, turno e faixa.

## Como usar durante a matheuristica

Antes de alterar o solver, rode a suite para confirmar o estado atual. Depois
de cada adaptacao, rode novamente. Quando a matheuristica ganhar funcoes puras
para solucao inicial, vizinhancas, fixacao de variaveis ou avaliacao de custo,
adicione testes novos em `tests/` mantendo estes casos como referencia do
comportamento esperado do projeto atual.
