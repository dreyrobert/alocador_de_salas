# Organizacao dos resultados

Esta pasta guarda arquivos gerados por execucoes do modelo e por scripts de
analise. A separacao abaixo evita misturar solucoes operacionais, candidatos
temporarios e experimentos.

## `fix_and_optimize/`

Saidas padrao de `alocador_salas.optimization.main_fix_and_optimize`.

- `melhor_solucao_fix_and_optimize.sol`: melhor solucao encontrada pela rotina.
- `solution.sol`: solucao historica que antes ficava na raiz do projeto.
- `historico_fix_and_optimize.csv` e `historico_fix_and_optimize.json`:
  historico das tentativas, incluindo ciclo, tipo e recurso da vizinhanca.

## `fix_and_optimize/candidatos/`

Arquivos `.sol` candidatos gerados durante uma passada.

Os arquivos seguem o formato `candidato_<TIPO>_<RECURSO>.sol`, por exemplo
`candidato_curso_CC.sol` ou `candidato_dia_turno_2_M.sol`. Cada um e a solucao
produzida ao liberar temporariamente as disciplinas da vizinhanca e fixar as
demais.

Por padrao, a rotina mantem esses candidatos apenas em memoria e salva somente
a melhor solucao final. Use `--salvar-candidatos` para gerar estes arquivos de
debug.

A rotina completa constroi o modelo Gurobi uma unica vez. A cada vizinhanca, ela
libera as fixacoes anteriores das variaveis `x`, aplica a incumbente atual como
MIP start e fixa somente as variaveis fora da vizinhanca corrente.

## `experimentos/`

Consulte o [índice dos experimentos](experimentos/README.md) para localizar as rodadas pelos parâmetros.

Resultados de rodadas comparativas ou execucoes nomeadas. Quando o experimento
for especifico de um semestre, use uma subpasta, por exemplo `2024_1/`.

## `diagnosticos/`

Planilhas e relatorios auxiliares para analisar solucoes, vizinhancas e metricas
do problema.
