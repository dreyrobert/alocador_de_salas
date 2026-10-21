# Organizacao dos dados

Esta pasta guarda os arquivos de entrada usados pelo modelo e pelos scripts.

## `<semestre>/`

Cada semestre tem sua propria pasta: `2022_1/`, `2022_2/`, `2023_1/`,
`2023_2/` e `2024_1/`.

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

## `exemplos/`

Arquivos pequenos para execucoes manuais e testes locais.

## `../web/static/dados/`

Arquivos servidos ou gerados pela interface web. Eles ficam separados dos dados
de entrada para evitar misturar upload/download da aplicacao com bases de
experimento.
