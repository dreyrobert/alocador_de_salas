# Organizacao dos dados

Esta pasta guarda os arquivos de entrada usados pelo modelo e pelos scripts.

## `<semestre>/`

Cada semestre tem sua propria pasta: `2022_1/`, `2022_2/`, `2023_1/`,
`2023_2/`, `2024_1/`, `2024_2/`, `2025_1/`, `2025_2/`, `2026_1/` e `2026_2/`.

Os arquivos seguem o padrao:

- `horarios_<semestre>.xlsx`
- `salas_<semestre>.csv`
- `salas_preferenciais_<ano>.<periodo>.xlsx`
- `solucao_<semestre>.xlsx`, quando houver uma solucao conhecida.

Os comandos individuais usam `2024_1` como padrao. Para rodar a bateria de
experimentos de outro semestre, execute na raiz do projeto, por exemplo:

```bash
uv run python scripts/run_fixopt_semestre.py --semestre 2022_1
```

A coluna `vagas` dos horários define a demanda usada na restrição de capacidade
das salas. Quando a coluna não existe ou a célula está vazia, o leitor assume
**25 alunos por turma**, conforme a hipótese usada no código histórico. Valores
informados, inclusive zero, são preservados. Os 25 alunos são uma hipótese de
experimentação, não uma quantidade observada nesses semestres.

Para novos semestres, crie a pasta e adicione as tres entradas seguindo os
nomes acima. O script encontra os caminhos automaticamente.

Quando a planilha de horários possui `num_turma`, o identificador usado é
`<cod>_<num_turma>`. O número deve ser um inteiro positivo e o par
`(cod, num_turma)` não pode se repetir, mesmo em disciplinas agrupadas.
Se a coluna não existir, o leitor mantém a numeração histórica por ordem de
ocorrência de cada código. Células vazias em uma coluna existente são erros.

As bases de `2024_2` em diante possuem `num_turma`. Soluções geradas antes
desse suporte precisam ter a correspondência das turmas verificada antes de
serem reutilizadas, pois o contador antigo pode atribuir o mesmo ID a outra turma.

## `exemplos/`

Arquivos pequenos para execucoes manuais e testes locais.

## `../web/static/dados/`

Arquivos servidos ou gerados pela interface web. Eles ficam separados dos dados
de entrada para evitar misturar upload/download da aplicacao com bases de
experimento.
