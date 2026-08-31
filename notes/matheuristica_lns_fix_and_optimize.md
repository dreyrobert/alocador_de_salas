# Possibilidades para uma Matheuristica LNS com Fix-and-Optimize

Este documento registra possibilidades em alto nivel para evoluir o alocador atual de salas para uma matheuristica baseada em LNS (Large Neighborhood Search) com uma estrategia de fix-and-optimize.

No codigo atual, a solucao do problema e representada principalmente pelas variaveis:

```text
x[d, s, h] = 1 se a disciplina d e alocada na sala s no horario h
```

Assim, uma estrategia natural e manter grande parte dessas variaveis fixadas e liberar apenas um subconjunto delas para reotimizacao via PLI.

## 1. Gerar uma solucao inicial

A solucao inicial deve fornecer uma alocacao viavel ou parcialmente viavel para servir como ponto de partida da busca local. Como o modelo atual ja permite nao alocar disciplinas mediante penalidade, a primeira versao da matheuristica pode trabalhar com solucoes completas ou incompletas.

### Possibilidade A: usar o PLI atual com limite de tempo reduzido

Executar o modelo atual por um tempo menor, por exemplo 1, 5 ou 10 minutos, e usar a melhor solucao encontrada como ponto inicial.

Vantagens:

- Reaproveita quase totalmente o `solve.py`.
- Gera uma solucao inicial ja alinhada com a funcao objetivo atual.
- Facilita comparar a matheuristica com o modelo original.

Desvantagens:

- Ainda depende do Gurobi para construir a primeira solucao.
- Em instancias maiores, pode demorar para encontrar uma solucao boa.
- Se o modelo nao encontrar solucao incumbente, a heuristica fica sem ponto inicial.

Recomendacao:

Esta e a melhor opcao para a primeira versao, porque reduz o risco de implementacao. Depois, pode ser comparada com uma construcao gulosa.

### Possibilidade A.1: usar um PLI simplificado para encontrar a primeira solucao

Uma alternativa mais proxima da literatura de fix-and-optimize e gerar a solucao inicial com uma versao simplificada do modelo. A ideia e remover temporariamente partes da funcao objetivo que tornam o problema mais dificil, mantendo as restricoes essenciais.

No contexto deste projeto, a solucao inicial poderia priorizar:

```text
- respeitar conflito de sala e horario;
- respeitar capacidade das salas;
- evitar disciplinas nao alocadas;
- evitar salas nao preferenciais, se isso nao dificultar demais.
```

E poderia deixar para a etapa LNS os criterios mais refinados:

```text
- reduzir dispersao de salas por fase;
- reduzir dispersao de salas por curso;
- reduzir quantidade de salas diferentes por disciplina/fase/curso.
```

Vantagens:

- Aproxima o metodo da estrategia usada no artigo, que remove objetivos/restricoes dificeis para obter uma solucao inicial rapidamente.
- Tende a encontrar uma incumbente mais cedo.
- Separa bem duas preocupacoes: primeiro viabilidade, depois qualidade.

Desvantagens:

- Exige parametrizar a funcao objetivo do `solve.py`.
- A solucao inicial pode ser pior em termos de distancia e concentracao espacial.

Recomendacao:

Boa opcao para a versao academica do metodo. Para implementacao, pode ser feita criando um parametro como `modo_objetivo="inicial"` e outro como `modo_objetivo="completo"`.

### Possibilidade B: heuristica gulosa por disciplina

Ordenar as disciplinas e tentar alocar cada uma na melhor sala disponivel, respeitando capacidade e conflito de horario.

Uma ordem possivel:

```text
1. disciplinas com menos salas compativeis;
2. disciplinas com maior numero de alunos;
3. disciplinas com mais horarios;
4. disciplinas com salas preferenciais mais restritas.
```

Para cada disciplina, testar salas candidatas e escolher a que gera menor penalidade:

```text
custo = penalidade por sala nao preferencial
      + penalidade por aumentar dispersao da fase
      + penalidade por aumentar dispersao do curso
      + penalidade por trocar de sala entre horarios da mesma disciplina
```

Vantagens:

- Muito rapida.
- Independe do Gurobi para iniciar.
- Boa para gerar uma solucao sempre que o PLI inicial falhar.

Desvantagens:

- Pode produzir solucoes ruins.
- Exige reimplementar parte da logica de avaliacao da funcao objetivo.
- Pode ficar presa cedo em escolhas locais ruins.

Recomendacao:

Boa como fallback ou segunda etapa do trabalho.

### Possibilidade C: solucao historica ou manual

Usar planilhas de semestres anteriores ou uma alocacao manual como solucao inicial, quando houver compatibilidade com os dados atuais.

Vantagens:

- Pode partir de uma solucao realista.
- Interessante academicamente se o objetivo for melhorar uma solucao usada pela instituicao.

Desvantagens:

- Depende de compatibilidade entre disciplinas, salas e horarios.
- Exige parser de solucao externa.
- Pode ter muitos dados ausentes ou divergentes.

Recomendacao:

Interessante para experimentos, mas nao para a primeira implementacao.

## 2. Gerar as vizinhancas das solucoes

Na LNS, uma vizinhanca e definida por quais partes da solucao serao liberadas para reotimizacao. No fix-and-optimize, as demais variaveis ficam fixadas no valor atual.

No codigo atual, isso significa:

```text
Para disciplinas fixas:
    x[d, s, h] = valor atual

Para disciplinas liberadas:
    x[d, s, h] continua livre para o Gurobi decidir
```

Tambem e possivel liberar salas ou horarios em vez de disciplinas, mas liberar disciplinas tende a encaixar melhor no modelo atual.

### Recursos conectados

Uma ideia importante da literatura de LNS com fix-and-optimize e nao liberar variaveis isoladas sem criterio. O ideal e liberar conjuntos de variaveis que estejam conectadas, isto e, variaveis que provavelmente precisam mudar juntas para melhorar a solucao.

No artigo, essa conectividade e tratada por meio de recursos. f Neste projeto, recursos naturais seriam:

```text
curso;
fase;
disciplina;
dia/turno;
sala;
bloco;
grupo de disciplinas problematicas.
```

Cada recurso gera um conjunto de variaveis:

```text
X(recurso) = conjunto de variaveis x[d, s, h] associadas ao recurso
```

Exemplos:

```text
X(CC) = todas as variaveis x[d, s, h] das disciplinas de Ciencia da Computacao
X(CC_3) = todas as variaveis x[d, s, h] das disciplinas da terceira fase de CC
X(SEG-M) = variaveis das disciplinas que possuem aula segunda de manha
```

O criador de vizinhanca pode seguir a mesma logica do artigo:

```text
1. escolher um recurso inicial aleatoriamente;
2. adicionar recursos conectados ao recurso inicial;
3. parar quando o numero de variaveis liberadas atingir o tamanho desejado da vizinhanca;
4. liberar todas as variaveis x[d, s, h] associadas aos recursos escolhidos.
```

Isso evita vizinhancas pequenas demais ou sem relacao com a estrutura real do problema.

### Funcoes de score para conectividade

Para escolher recursos conectados, pode-se definir uma funcao de score. Quanto maior o score entre um recurso candidato e o conjunto ja escolhido, maior a chance de esse recurso ser adicionado a vizinhanca.

Scores possiveis para este projeto:

```text
score_por_curso:
    alto quando disciplinas pertencem ao mesmo curso.

score_por_fase:
    alto quando disciplinas pertencem ao mesmo curso e fase.

score_por_horario:
    alto quando disciplinas disputam os mesmos dias/turnos/faixas.

score_por_demanda:
    alto quando disciplinas possuem numeros de alunos semelhantes,
    pois tendem a disputar salas de capacidade parecida.

score_por_preferencia:
    alto quando disciplinas possuem salas preferenciais em comum.

score_por_solucao_atual:
    alto quando disciplinas contribuem para o custo atual,
    por exemplo por nao alocacao, sala nao preferencial ou dispersao.
```

Uma versao simples de score agregado poderia ser:

```text
score(d, R) =
    5 * mesma_fase(d, R)
  + 3 * mesmo_curso(d, R)
  + 3 * conflito_ou_sobreposicao_de_horario(d, R)
  + 2 * salas_preferenciais_em_comum(d, R)
  + 1 * demanda_semelhante(d, R)
  + penalidade_atual(d)
```

Essa funcao nao precisa ser perfeita. Ela serve como heuristica para criar subproblemas com variaveis que fazem sentido juntas.

### Vizinhanca A: por curso

Liberar todas as disciplinas de um curso por vez.

Exemplos:

```text
liberar todas as disciplinas de CC
liberar todas as disciplinas de ADM
liberar todas as disciplinas de MED
```

Vantagens:

- Encaixa bem com os termos de distancia por curso.
- Facil de implementar usando `disciplinas[d].curso`.
- Pode melhorar a concentracao espacial de um curso.

Desvantagens:

- Alguns cursos podem gerar subproblemas grandes demais.
- Pode nao corrigir conflitos entre cursos diferentes.

Uso recomendado:

Boa vizinhanca estrutural para a primeira versao.

### Vizinhanca B: por fase

Liberar disciplinas de uma fase especifica de um curso.

Exemplo:

```text
liberar CC_3
liberar ADM_5
liberar MED_8
```

Vantagens:

- Encaixa diretamente com `fases` e com a penalidade de distancia por fase.
- Subproblemas menores que a vizinhanca por curso.
- Ajuda a aproximar salas usadas por estudantes da mesma fase.

Desvantagens:

- Pode ser pequena demais em alguns casos.
- Melhorias podem ser limitadas se as salas ocupadas por outras fases continuarem fixas.

Uso recomendado:

Provavelmente a vizinhanca mais adequada para comecar.

### Vizinhanca C: por dia e turno

Liberar todas as disciplinas que possuem aula em determinado dia e turno.

Exemplos:

```text
segunda de manha
quarta a tarde
sexta a noite
```

Vantagens:

- Ataca diretamente conflitos de sala e horario.
- Natural para o problema de alocacao.
- Pode melhorar encaixes locais de uso das salas.

Desvantagens:

- Uma disciplina com varios horarios pode atravessar diferentes dias/turnos.
- Se liberar apenas parte dos horarios de uma disciplina, pode prejudicar a consistencia da alocacao.

Uso recomendado:

Usar liberando disciplinas inteiras que tenham pelo menos um horario no dia/turno escolhido.

### Vizinhanca D: disciplinas problematicas

Liberar disciplinas que estao contribuindo mais para o custo da solucao.

Criterios possiveis:

```text
- disciplinas nao alocadas;
- disciplinas parcialmente alocadas;
- disciplinas em salas nao preferenciais;
- disciplinas que usam muitas salas diferentes;
- disciplinas de fases/cursos com grande dispersao de salas;
- disciplinas envolvidas em conflitos detectados na verificacao.
```

Vantagens:

- Foca onde ha maior potencial de melhoria.
- Tende a ser eficiente computacionalmente.
- Dialoga bem com a funcao objetivo atual.

Desvantagens:

- Exige uma funcao para decompor o custo da solucao.
- Pode ficar repetindo sempre os mesmos elementos se nao houver diversificacao.

Uso recomendado:

Muito importante para uma segunda versao, depois que a estrutura basica estiver funcionando.

### Vizinhanca E: bloco aleatorio controlado

Escolher aleatoriamente um percentual de disciplinas para liberar.

Exemplo:

```text
liberar 5%, 10% ou 20% das disciplinas
```

Vantagens:

- Ajuda a escapar de otimos locais.
- Simples de implementar.
- Boa para diversificacao.

Desvantagens:

- Pode gerar subproblemas sem sentido estrutural.
- Pode gastar tempo em regioes pouco promissoras.

Uso recomendado:

Usar intercalada com vizinhancas estruturais.

## 3. Escolher o proximo vizinho da solucao

A escolha do proximo vizinho define qual subproblema sera otimizado em cada iteracao da LNS.

### Estrategia A: ordem ciclica

Percorrer uma lista fixa de vizinhancas.

Exemplo:

```text
CC_1, CC_2, CC_3, ..., ADM_1, ADM_2, ...
```

Vantagens:

- Simples.
- Reprodutivel.
- Facil de explicar no TCC.

Desvantagens:

- Pouca adaptacao ao comportamento da busca.
- Pode gastar tempo em regioes que nao melhoram a solucao.

Recomendacao:

Boa para a primeira implementacao.

### Estrategia B: melhor melhoria encontrada

Testar varios vizinhos candidatos e escolher aquele que gera a maior reducao de custo.

Vantagens:

- Tende a produzir melhoria mais forte por iteracao.
- Boa para comparar qualidade de vizinhancas.

Desvantagens:

- Muito mais cara computacionalmente.
- Pode exigir resolver muitos subproblemas por iteracao.

Recomendacao:

Usar apenas em experimentos pequenos ou com limite de tempo muito curto por subproblema.

### Estrategia C: primeira melhoria

Percorrer vizinhos candidatos e aceitar o primeiro que melhora a solucao.

Vantagens:

- Mais rapida que melhor melhoria.
- Simples de implementar.∏
- Reduz tempo gasto por iteracao.

Desvantagens:

- Pode aceitar melhorias pequenas e deixar melhorias maiores para depois.

Recomendacao:
Boa estrategia principal apos a versao ciclica.

### Estrategia D: escolha adaptativa

Atribuir pesos para cada tipo de vizinhanca conforme seu desempenho historico.

Exemplo:

```text
se vizinhancas por fase melhoram muito, aumentar chance de escolher fase;
se vizinhancas aleatorias nao melhoram, reduzir sua chance temporariamente.
```

Vantagens:

- Mais sofisticada.
- Pode melhorar desempenho em diferentes instancias.
- Boa contribuicao academica se houver tempo para experimentos.

Desvantagens:

- Mais dificil de implementar e justificar.
- Exige cuidado para nao deixar a metodologia complexa demais.

Recomendacao:

Deixar como evolucao, nao como primeira entrega.

### Estrategia E: escolha aleatoria uniforme entre tipos de vizinhanca

Escolher aleatoriamente qual tipo de vizinhanca sera usado em cada iteracao.

Exemplo:

```text
N = {curso, fase, dia_turno, problematicas, aleatoria}
vizinhanca_escolhida = sorteio_uniforme(N)
```

Vantagens:

- Fica bastante alinhada ao artigo usado como referencia.
- Evita que a busca fique presa sempre no mesmo tipo de movimento.
- E simples de implementar e explicar.

Desvantagens:

- Pode gastar iteracoes em vizinhancas pouco promissoras.
- Nao usa aprendizado sobre quais vizinhancas estao funcionando melhor.

Recomendacao:

Boa escolha para uma versao inspirada diretamente no artigo. A escolha adaptativa pode aparecer como melhoria futura.

## 4. Tamanho adaptativo da vizinhanca

O tamanho da vizinhanca define quantas variaveis serao liberadas em cada subproblema. Se poucas variaveis forem liberadas, o subproblema fica facil, mas pode nao ter espaco para melhorar. Se muitas variaveis forem liberadas, o subproblema fica parecido com o modelo completo e pode ficar dificil demais.

Uma forma simples de controlar isso e usar o `MIPGap` retornado pelo Gurobi ao final de cada subproblema.

Ideia:

```text
se MIPGap > MaxGap:
    o subproblema esta dificil demais
    reduzir o tamanho da vizinhanca

se MIPGap < MinGap:
    o subproblema esta facil demais
    aumentar o tamanho da vizinhanca
```

Parametros possiveis:

```text
MinGap = 0.01
MaxGap = 0.10
Decay = 0.10
```

Atualizacao:

```text
se gap_suavizado > MaxGap:
    S = S * (1 - Decay)

se gap_suavizado < MinGap:
    S = S * (1 + Decay)
```

Aqui, `S` representa o tamanho da vizinhanca, medido pelo numero de variaveis `x[d, s, h]` liberadas ou pelo numero de disciplinas liberadas.

Como cada tipo de vizinhanca pode ter dificuldade diferente, o ideal e manter um tamanho separado para cada uma:

```text
S_curso
S_fase
S_dia_turno
S_problematicas
S_aleatoria
```

Para evitar oscilacao excessiva, tambem e possivel suavizar o gap:

```text
gap_suavizado_atual =
    alpha * gap_observado_atual
  + (1 - alpha) * gap_suavizado_anterior
```

Valor inicial sugerido:

```text
alpha = 0.30
```

Essa etapa e interessante academicamente porque transforma o metodo em uma busca mais autonoma, capaz de ajustar a dificuldade dos subproblemas ao longo da execucao.

## Desenho recomendado para a primeira versao

Uma primeira versao viavel e defendivel pode seguir este fluxo:

```text
1. Ler dados usando ExtraiSalas e ExtraiHorariosAula.
2. Gerar solucao inicial com o PLI atual em modo simplificado ou com limite de tempo reduzido.
3. Salvar a solucao atual como valores de x[d, s, h].
4. Fixar todas as variaveis x[d, s, h] conforme a solucao inicial.
5. Repetir ate atingir limite de tempo ou iteracoes:
   5.1. sortear um tipo de vizinhanca;
   5.2. escolher recursos conectados ate atingir o tamanho S da vizinhanca;
   5.3. desfixar as variaveis x[d, s, h] associadas aos recursos escolhidos;
   5.4. manter fixadas as demais variaveis;
   5.5. resolver o subproblema com Gurobi por tempo curto;
   5.6. se melhorar o custo global, atualizar a solucao incumbente;
   5.7. atualizar o tamanho S da vizinhanca com base no MIPGap;
   5.8. fixar novamente as variaveis conforme a nova solucao incumbente.
6. Exportar a melhor solucao encontrada.
```

Parametros iniciais sugeridos:

```text
tempo para solucao inicial: 60 a 300 segundos
tempo por subproblema: 10 a 60 segundos
tamanho inicial da vizinhanca: 5% a 15% das variaveis x[d, s, h] ou disciplinas equivalentes
criterio de parada: tempo total, numero de iteracoes ou iteracoes sem melhoria
MinGap: 0.01
MaxGap: 0.10
Decay: 0.10
alpha para suavizacao do gap: 0.30
```

## Adaptacoes necessarias no codigo atual

Para implementar essa abordagem, o `solve.py` deveria ser refatorado em funcoes menores.

Sugestao de separacao:

```text
carregar_dados(...)
construir_modelo(...)
resolver_modelo(...)
extrair_solucao(...)
avaliar_solucao(...)
fixar_variaveis(...)
exportar_solucao(...)
```

Mudancas importantes:

```text
- o modelo deve retornar a solucao em memoria, nao apenas gerar planilha;
- o status do Gurobi deve ser tratado antes de acessar x[d, s, h].X;
- deve existir uma forma de receber uma solucao incumbente;
- deve existir uma forma de fixar variaveis fora da vizinhanca;
- deve existir uma forma de desfixar variaveis associadas a recursos escolhidos;
- deve existir controle do tamanho da vizinhanca por tipo de vizinhanca;
- deve-se reaproveitar a mesma instancia do modelo quando possivel, alterando bounds das variaveis;
- a funcao objetivo deve poder ser avaliada fora do Gurobi para comparar solucoes.
```

## Observacao academica

O nome mais adequado para a abordagem e:

```text
matheuristica baseada em Large Neighborhood Search com reotimizacao local por Fix-and-Optimize
```

Essa formulacao deixa claro que o metodo nao abandona o PLI. Em vez disso, usa o PLI como mecanismo exato para resolver subproblemas menores dentro de uma estrategia heuristica maior.
