# Experimentos 2024_1

Esta pasta guarda os artefatos dos experimentos da instancia `2024_1`, separados por finalidade.

## Estrutura

- `analises/`: CSVs consolidados usados para comparar execucoes e preparar tabelas.
- `fixopt_4h/`: execucoes Fix-and-Optimize com orcamento total de 4 horas.
- `fixopt_300s/`: execucoes Fix-and-Optimize com orcamento total de 300 segundos.
- `pli_4h/`: execucoes PLI/Gurobi com orcamento de 4 horas.
- `pli_300s/`: execucoes PLI/Gurobi com orcamento de 300 segundos.
- `solucoes_avulsas/`: arquivos `.sol` sem o conjunto completo de CSV/JSON/log correspondente nesta pasta.

## Convencoes rapidas

- `.csv`: resumo tabular ou historico por iteracao.
- `.json`: resumo estruturado da execucao Fix-and-Optimize.
- `.out`: saida completa do terminal/log da execucao.
- `.sol`: solucao exportada pelo Gurobi.

Observacao: os logs `.out` e alguns `.json` podem citar o caminho antigo direto em
`resultados/experimentos/2024_1/`, porque esse era o destino no momento da execucao.
Esses conteudos foram preservados como registro original do experimento.

## Arquivos mais uteis

- `analises/analise_comparativa_4h.csv`: comparacao principal das rodadas de 4 horas.
- `analises/analise_vizinhancas_fixopt_4h.csv`: analise por tipo de vizinhanca nas rodadas Fix-and-Optimize de 4 horas.
- `analises/resumo_experimentos_fixopt_vs_pli.csv`: resumo comparando Fix-and-Optimize e PLI.
- `analises/detalhe_passadas_fixopt.csv`: detalhe das passadas das rodadas Fix-and-Optimize de 300 segundos.
