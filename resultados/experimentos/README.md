# Índice dos experimentos

## Comparação atual: ordem dos cursos

Pasta: [2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min](2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/).

| Ordem | Inicial | Final | Tempo observado | Situação |
| --- | ---: | ---: | ---: | --- |
| Alfabética (referência anterior) | 186694.5 | 186275.5 | 221.28s | CONCLUIDO |
| Maior demanda (23/09) | 186694.5 | 186275.5 | 247.29s | CONCLUIDO |
| Aleatória, seed 42 (23/09) | 186761.5 | 186186.5 | 247.89s | CONCLUIDO |

Orçamento por execução: 4h; inicial: 180s; NoRel inicial: 180s; vizinhança: até 600s. Os dois limites iniciais atuam na mesma etapa, não são somados. O algoritmo pode encerrar antes de 4h por ausência de melhoria. Valores extraídos dos resumos finais dos logs. A aleatória começou 67 pontos acima da referência; mesmo objetivo inicial, por sua vez, não prova que as alocações iniciais sejam idênticas.

## Como encontrar os arquivos

- `2024_1/ordem_cursos/`: comparação atual e rodadas históricas de ordenação.
- `2024_1/outras_vizinhancas/`: dia/turno e híbrida.
- `2024_1/fixopt_historico/`: outros orçamentos e configurações de F&O.
- `2024_1/pli/`: execuções do modelo completo.
- [2024_1/analises/](2024_1/analises/): tabelas consolidadas anteriores; não incluem automaticamente as novas rodadas.
- `parametros_incompletos/` e `2024_1/parametros_incompletos/`: evidência insuficiente para nomear todos os parâmetros.
- `2024_1/solucoes_avulsas/`: soluções sem conjunto completo de logs.
- `tentativas_com_erro/`: tentativas que falharam antes de gerar resultados.

Os nomes indicam limites, não duração efetiva. `viz_tempo_restante` descreve os limites observados; não implica um teto nominal comprovado. `nao_registrado` significa que o parâmetro não foi confirmado nos artefatos. Os nomes antigos dos arquivos foram mantidos para rastreabilidade.

## Todas as execuções organizadas

| Pasta | Parâmetros e evidência |
| --- | --- |
| [2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/alfabetica_referencia](2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/alfabetica_referencia/) | Referência alfabética. Total de 4h indicado no nome original; inicial e NoRel de 180s e vizinhança de 600s confirmados no log. |
| [2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/maior_demanda_20260923_185629](2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/maior_demanda_20260923_185629/) | Rodada de 23/09/2026. Total de 14400s conforme comando desta sessão; inicial e NoRel de 180s, vizinhança de 600s confirmados no log. Seed 42 apenas na ordenação aleatória. |
| [2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/aleatoria_seed42_20260923_185629](2024_1/ordem_cursos/total4h_inicial3min_norel3min_viz10min/aleatoria_seed42_20260923_185629/) | Rodada de 23/09/2026. Total de 14400s conforme comando desta sessão; inicial e NoRel de 180s, vizinhança de 600s confirmados no log. Seed 42 apenas na ordenação aleatória. |
| [2024_1/outras_vizinhancas/total4h_inicial3min_norel3min_viz10min/dia_turno](2024_1/outras_vizinhancas/total4h_inicial3min_norel3min_viz10min/dia_turno/) | Total de 4h indicado no nome original; inicial e NoRel de 180s e vizinhança de 600s confirmados no log. |
| [2024_1/outras_vizinhancas/total4h_inicial3min_norel3min_viz10min/hibrida](2024_1/outras_vizinhancas/total4h_inicial3min_norel3min_viz10min/hibrida/) | Total de 4h indicado no nome original; inicial e NoRel de 180s e vizinhança de 600s confirmados no log. |
| [2024_1/fixopt_historico/total4h_inicial5min_norel5min_viz_tempo_restante/curso_alfabetica](2024_1/fixopt_historico/total4h_inicial5min_norel5min_viz_tempo_restante/curso_alfabetica/) | Inicial e NoRel de 300s. O primeiro limite de vizinhança registrado foi 14096.69s (tempo restante), NÃO 600s. Total de 4h indicado no nome original. |
| [2024_1/fixopt_historico/total5min_inicial1min_norel1min_viz_tempo_restante/curso_alfabetica_uma_passada](2024_1/fixopt_historico/total5min_inicial1min_norel1min_viz_tempo_restante/curso_alfabetica_uma_passada/) | Total de 300s indicado no nome original. Inicial e NoRel confirmados no log. Limites de vizinhança diminuem com o tempo restante; teto nominal não registrado. Uma passada observada. |
| [2024_1/fixopt_historico/total5min_inicial2min_norel2min_viz_tempo_restante/curso_alfabetica_uma_passada](2024_1/fixopt_historico/total5min_inicial2min_norel2min_viz_tempo_restante/curso_alfabetica_uma_passada/) | Total de 300s indicado no nome original. Inicial e NoRel confirmados no log. Limites de vizinhança diminuem com o tempo restante; teto nominal não registrado. Uma passada observada. |
| [2024_1/fixopt_historico/total5min_inicial3min_norel3min_viz_tempo_restante/curso_alfabetica_uma_passada](2024_1/fixopt_historico/total5min_inicial3min_norel3min_viz_tempo_restante/curso_alfabetica_uma_passada/) | Total de 300s indicado no nome original. Inicial e NoRel confirmados no log. Limites de vizinhança diminuem com o tempo restante; teto nominal não registrado. Uma passada observada. |
| [2024_1/fixopt_historico/total5min_inicial4min_norel4min_viz_tempo_restante/curso_alfabetica_uma_passada](2024_1/fixopt_historico/total5min_inicial4min_norel4min_viz_tempo_restante/curso_alfabetica_uma_passada/) | Total de 300s indicado no nome original. Inicial e NoRel confirmados no log. Limites de vizinhança diminuem com o tempo restante; teto nominal não registrado. Uma passada observada. |
| [2024_1/fixopt_historico/total5min_inicial3min_norel_nao_registrado_viz_tempo_restante/curso_alfabetica_sem_log](2024_1/fixopt_historico/total5min_inicial3min_norel_nao_registrado_viz_tempo_restante/curso_alfabetica_sem_log/) | Total 300s e inicial 180s indicados no nome original, sem .out para confirmar. NoRel não registrado. Histórico registra limites decrescentes de vizinhança. |
| [2024_1/parametros_incompletos/experimento_fixopt_300_sem_log](2024_1/parametros_incompletos/experimento_fixopt_300_sem_log/) | Nome original contém 300, mas não permite distinguir com segurança o orçamento total do tempo inicial. Sem .out; parâmetros não confirmados. |
| [2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/alfabetica](2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/alfabetica/) | Inicial e NoRel confirmados no log, independentemente do nome antigo da pasta. Vizinhança de 600s. O limite total não consta dos artefatos desta execução; não inferir pela duração observada. A comparação antiga foi descrita como 2h, mas isso não comprova o comando de cada arquivo atual. |
| [2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/aleatoria_seed42](2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/aleatoria_seed42/) | Inicial e NoRel confirmados no log, independentemente do nome antigo da pasta. Vizinhança de 600s. O limite total não consta dos artefatos desta execução; não inferir pela duração observada. A comparação antiga foi descrita como 2h, mas isso não comprova o comando de cada arquivo atual. |
| [2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/maior_demanda2](2024_1/ordem_cursos/historico_total_nao_registrado_inicial3s_norel3s_viz10min/maior_demanda2/) | Inicial e NoRel confirmados no log, independentemente do nome antigo da pasta. Vizinhança de 600s. O limite total não consta dos artefatos desta execução; não inferir pela duração observada. A comparação antiga foi descrita como 2h, mas isso não comprova o comando de cada arquivo atual. |
| [2024_1/ordem_cursos/historico_total_nao_registrado_inicial180s_norel180s_viz10min/maior_demanda](2024_1/ordem_cursos/historico_total_nao_registrado_inicial180s_norel180s_viz10min/maior_demanda/) | Inicial e NoRel confirmados no log, independentemente do nome antigo da pasta. Vizinhança de 600s. O limite total não consta dos artefatos desta execução; não inferir pela duração observada. A comparação antiga foi descrita como 2h, mas isso não comprova o comando de cada arquivo atual. |
| [2024_1/pli/total4h_base](2024_1/pli/total4h_base/) | TimeLimit=14400 confirmado no log. Sem configuração explícita de MIPFocus/NoRel encontrada no log. |
| [2024_1/pli/total4h_mipfocus1_norel5min](2024_1/pli/total4h_mipfocus1_norel5min/) | TimeLimit=14400, MIPFocus=1, NoRelHeurTime=300 confirmados no log. Não há reotimização de vizinhanças. |
| [2024_1/pli/total5min_mipfocus1_norel5min](2024_1/pli/total5min_mipfocus1_norel5min/) | TimeLimit=300, MIPFocus=1, NoRelHeurTime=300 confirmados no log. Não há reotimização de vizinhanças. |
| [tentativas_com_erro/20260923_185530_bash_array_vazio](tentativas_com_erro/20260923_185530_bash_array_vazio/) | Falha EXTRA[@]: unbound variable antes de iniciar o solver. Não é resultado de experimento. |
| [parametros_incompletos/exportacao_gurobi_20260805_191345](parametros_incompletos/exportacao_gurobi_20260805_191345/) | Exportação histórica isolada; configuração e instância não verificadas nesta organização. |

[Mapa de caminhos antigos → novos e SHA-256](mapa_reorganizacao.json). Logs, CSVs, JSONs e soluções não tiveram seus conteúdos alterados. Referências internas antigas permanecem como registro histórico.
