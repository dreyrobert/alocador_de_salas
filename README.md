
#  Alocador de salas

  

Esse projeto tem como objetivo resolver o **Problema de Alocação de Salas (PAS)** na Universidade Federal da Fronteira Sul (UFFS), Campus Chapecó.

O PAS consiste em alocar salas para aulas/turmas com horários pré-determinados. A alocação deve ser feita seguindo restrições e preferências que podem variar de acordo com a particularidade do cenário onde o problema está sendo resolvido. 

Essa aplicação utiliza de um modelo matemático e de Programação Linear Inteira para resolver o PAS no cenário da UFFS, Campus Chapecó, além disso, conta com uma interface web para facilitar o uso do usuário.

[//]: # (Essa aplicação utiliza do modelo matemático descrito no trabalho de conclusão de curso [link pro cara] para resolver o PAS no cenário da UFFS, Campus Chapecó, além disso, conta com uma interface web para facilitar o uso do usuário.)


  

#  Requisitos

*  Python >= 3.10 e < 3.11

  

#  Instalação e configuração

Uma vez que os requisitos estão devidamente atendidos, podemos partir para a instalação

  

`uv sync`

Alternativamente, instale as dependencias com:

`pip3 install -r requirements.txt`

  

Com as dependências instaladas podemos partir para a configuração da aplicação.

  

-  Copie o arquivo `.env.example`, o renomeie para `.env` e preencha os campos presentes no arquivo

-  Também é necessário configurar o Gurobi, para informações mais detalhadas sobre sua instalação, configuração e licenças de uso acesse: https://support.gurobi.com/hc/en-us/articles/14799677517585-Getting-Started-with-Gurobi-Optimizer.

#  Estrutura de pastas

-  `dados/2024_1/`: dados de entrada padrao usados pelos scripts atuais.
-  `dados/historico/`: dados e solucoes de semestres anteriores.
-  `dados/exemplos/`: arquivos pequenos usados para testes manuais.
-  `src/alocador_salas/`: pacote Python com dominio, dados, otimizacao,
   relatorios e validacao.
-  `resultados/`: saidas geradas por execucoes, experimentos e diagnosticos.
-  `docs/notes/`: notas tecnicas e registros de analise.
-  `web/static/dados/`: arquivos usados ou gerados pela interface web.

  

#  Rodando a aplicação

  

Para rodar a interface web utilize o comando

`uv run python web/app.py`

Para rodar o modelo PLI diretamente:

`uv run alocador-salas-solve`

Para rodar a heuristica Fix-and-Optimize:

`uv run alocador-salas-fixopt`

Por padrao, a heuristica usa vizinhancas por curso. O tipo pode ser escolhido
pela linha de comando:

```bash
uv run alocador-salas-fixopt --tipo-vizinhanca curso
uv run alocador-salas-fixopt --tipo-vizinhanca curso_pares
uv run alocador-salas-fixopt --tipo-vizinhanca dia_turno
uv run alocador-salas-fixopt --tipo-vizinhanca dia_turno_curso
uv run alocador-salas-fixopt --tipo-vizinhanca hibrida
```

No modo hibrido, a busca explora cursos ate uma passada sem melhoria, tenta as
vizinhancas por dia e turno e volta aos cursos se encontrar uma nova incumbente.

No modo `curso_pares`, as passadas individuais se repetem enquanto houver
melhoria. Depois de uma passada individual inteira sem melhoria, executa uma
unica passada com todos os pares de cursos e encerra. Cada par libera todas as
disciplinas dos dois cursos e fixa as demais na melhor solucao atual. Os pares
seguem `--ordem-cursos` e `--seed`, sem repetir pares invertidos: para A, B e C,
a sequencia e A+B, A+C, B+C. Uma melhoria atualiza a incumbente em memoria antes
do proximo par. O historico identifica `par_cursos`, `curso_a`, `curso_b` e
`posicao_par`. O limite total pode interromper qualquer passada;
`--apenas-uma-passada` executa somente a primeira passada individual.

No modo `dia_turno_curso`, cada vizinhanca une todas as disciplinas do dia/turno
com todas as disciplinas de um curso presente naquele periodo. As disciplinas
sao liberadas por inteiro, incluindo aulas em outros dias e turnos. A passada
percorre os dias e turnos em ordem cronologica e, dentro de cada periodo, os
cursos em ordem alfabetica. Periodos vazios sao ignorados. `--ordem-cursos` e
`--seed` se aplicam aos modos `curso`, `curso_pares` e `hibrida`; a nova vizinhanca usa ordem
fixa. O historico registra dia, turno, curso, tamanhos, objetivos e tempos.

Novas execucoes de Fix-and-Optimize salvam automaticamente os parametros usados:
limites de tempo em segundos, tipo de vizinhanca, ordem e seed solicitadas e
efetivas, opcoes de execucao, caminhos de entrada/saida e parametros Gurobi
configurados para a solucao inicial e os subproblemas. O limite efetivo de cada
subproblema continua na coluna `tempo_limite_subproblema_s` do historico.
No CSV, as colunas `parametro_*` repetem a configuracao em cada iteracao; se nao
houver iteracoes, uma linha `tipo_registro=parametros` preserva a configuracao.
O JSON agora e um objeto com `versao_formato: 2`, `parametros` e `historico`
(a lista de iteracoes antes salva diretamente na raiz). Arquivos antigos nao
sao alterados.

### Hibridizacao de dia/turno + curso com pares de cursos

Os modos `hibrida_dia_turno_curso_pares` e `hibrida_pares_dia_turno_curso`
executam uma passada completa de cada tipo, na ordem indicada pelo nome.
A segunda etapa recebe a melhor solucao em memoria e acontece mesmo quando
nao ha melhoria na primeira. Um novo ciclo comeca se qualquer etapa melhorar;
um ciclo completo sem melhoria encerra a busca. O limite total pode interromper
qualquer etapa. `--apenas-uma-passada` executa somente a primeira etapa,
deixando o ciclo incompleto.

A etapa de dia/turno + curso usa ordem cronologica e cursos em ordem alfabetica.
A etapa de pares respeita `--ordem-cursos` e `--seed`. Os modos anteriores,
inclusive `curso_pares` e `hibrida`, conservam suas regras de transicao.

O historico inclui `etapa_no_ciclo`, `etapa_completa`, `ciclo_completo` e
`motivo_encerramento`. A conclusao indica que todas as vizinhancas previstas
foram processadas; nao exige que cada subproblema tenha sido provado otimo.
O JSON inclui ainda `ciclos` (numero, conclusao e quantidade de melhorias),
inclusive quando uma etapa nao possui vizinhancas. Os parametros registram a
sequencia e a ordem/seed efetiva por etapa. Um limite atingido antes de iniciar
a busca produz zero ciclos, com motivo `TEMPO_TOTAL`.

Exemplo de execucao das duas ordens no macOS, com inicial de 3 minutos,
subproblemas de ate 10 minutos e limite total de 4 horas por estrategia:

```bash
mkdir -p resultados/experimentos/2024_1/hibridas_dia_turno_curso_pares
for modo in hibrida_dia_turno_curso_pares hibrida_pares_dia_turno_curso; do
  caffeinate -i uv run alocador-salas-fixopt \
    --tipo-vizinhanca "$modo" --ordem-cursos alfabetica \
    --tempo-modelo 180 --tempo-heuristica 180 \
    --tempo-subproblema 600 --tempo-total 14400 \
    --salvar-solucao "resultados/experimentos/2024_1/hibridas_dia_turno_curso_pares/${modo}.sol" \
    --log-csv "resultados/experimentos/2024_1/hibridas_dia_turno_curso_pares/${modo}.csv" \
    --log-json "resultados/experimentos/2024_1/hibridas_dia_turno_curso_pares/${modo}.json" \
    > "resultados/experimentos/2024_1/hibridas_dia_turno_curso_pares/${modo}.out" 2>&1
done
```

Esses comandos geram uma solucao inicial em cada execucao. Limites iguais nao
garantem a mesma solucao inicial, nem mesmo quando os objetivos coincidem.
Portanto, servem para exploracao; uma comparacao controlada exige reutilizar
exatamente a mesma `SolucaoX` e objetivo inicial. A CLI atual nao possui opcao
para importar essa incumbente. Na API, o callback `resolver` permite devolver
uma copia do mesmo resultado inicial na primeira chamada de cada execucao e
encaminhar as chamadas seguintes para `resolver_modelo`. Ao comparar, registrar
tambem o custo de gerar essa inicial e o orcamento destinado a busca.
Comparar objetivo final, tempo, ciclos completos e ganho por etapa; destacar
execucoes cujo limite impediu a segunda etapa de terminar.
