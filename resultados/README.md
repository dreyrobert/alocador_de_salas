# Organizacao dos resultados

Esta pasta guarda arquivos gerados por execucoes do modelo e por scripts de
analise. A separacao abaixo evita misturar solucoes operacionais, candidatos
temporarios e experimentos.

## `fix_and_optimize/`

Saidas padrao de `main_fix_and_optimize.py`.

- `melhor_solucao_fix_and_optimize.sol`: melhor solucao encontrada pela rotina.
- `historico_fix_and_optimize.csv` e `historico_fix_and_optimize.json`:
  historico das tentativas por curso.

## `fix_and_optimize/candidatos/`

Arquivos `.sol` candidatos gerados durante uma passada por cursos.

Cada arquivo `candidato_curso_<CURSO>.sol` e a solucao produzida ao liberar
temporariamente as disciplinas daquele curso e fixar as demais. Se o objetivo
melhorar, esse candidato e copiado para a melhor solucao; se nao melhorar, ele
fica apenas como registro/debug da tentativa.

Por padrao, a rotina mantem esses candidatos apenas em memoria e salva somente
a melhor solucao final. Use `--salvar-candidatos` para gerar estes arquivos de
debug.

A rotina completa constroi o modelo Gurobi uma unica vez. A cada vizinhanca, ela
libera as fixacoes anteriores das variaveis `x`, aplica a incumbente atual como
MIP start e fixa somente as variaveis fora da vizinhanca corrente.

## `experimentos/`

Resultados de rodadas comparativas ou execucoes nomeadas. Quando o experimento
for especifico de um semestre, use uma subpasta, por exemplo `2024_1/`.

## `diagnosticos/`

Planilhas e relatorios auxiliares para analisar solucoes, vizinhancas e metricas
do problema.
