# Geracao de Vizinhancas para Solucoes Vizinhas

Este documento organiza ideias para gerar solucoes vizinhas no Problema de Alocacao de Salas (PAS) da UFFS, usando como referencia a abordagem de Large Neighborhood Search (LNS) com fix-and-optimize apresentada no artigo:

```text
Lindahl, Sorensen e Stidsen (2018)
A fix-and-optimize matheuristic for university timetabling
Journal of Heuristics, 24, 645-665.
DOI: 10.1007/s10732-018-9371-3
```

A ideia principal do artigo e manter grande parte da solucao atual fixa e liberar apenas um subconjunto de variaveis conectadas. Esse subconjunto define uma vizinhanca. Em seguida, o solver resolve um subproblema menor, tentando melhorar a solucao sem precisar resolver o modelo completo novamente.

No nosso modelo, a principal variavel de decisao e:

```text
x[d, s, h] = 1 se a disciplina d e alocada na sala s no horario h
```

Assim, gerar uma vizinhanca significa escolher quais variaveis `x[d, s, h]` serao liberadas para reotimizacao. Todas as demais variaveis permanecem fixadas com o valor da solucao atual.

## 1. Ideia Geral

Uma vizinhanca deve liberar conjuntos de variaveis que estejam conectadas. A intuicao e que algumas partes da solucao provavelmente precisam mudar juntas para que uma melhoria real aconteca.

Por exemplo, se uma disciplina de uma fase troca de sala, outras disciplinas da mesma fase podem precisar ser movidas tambem para manter as salas proximas. Da mesma forma, disciplinas com numero parecido de alunos tendem a disputar salas de capacidade semelhante, entao podem ser boas candidatas a troca.

Para estruturar isso, podemos usar o conceito de recurso.

Um recurso e uma entidade do problema associada a um conjunto de variaveis. Exemplos de recursos no nosso caso:

```text
- curso
- fase
- disciplina
- horario
- dia e turno
- sala
- bloco
- grupo de disciplinas problematicas
```

Cada recurso possui um conjunto de variaveis associado:

```text
X(recurso) = conjunto de variaveis x[d, s, h] associadas ao recurso
```

Exemplos:

```text
X(CC) = todas as variaveis x[d, s, h] das disciplinas do curso de Ciencia da Computacao
X(CC_1) = todas as variaveis x[d, s, h] das disciplinas da primeira fase de Ciencia da Computacao
X(segunda_manha) = variaveis das disciplinas que possuem aula na segunda-feira de manha
X(disciplina_problematica) = variaveis de disciplinas que contribuem muito para a penalidade atual
```

## 2. Algoritmo Basico Para Criar Uma Vizinhanca

A partir da ideia do artigo, uma forma simples de gerar uma vizinhanca e:

```text
1. Escolher um recurso inicial aleatoriamente.
2. Adicionar recursos conectados ao recurso inicial.
3. Parar quando o numero de variaveis liberadas atingir o tamanho desejado da vizinhanca.
4. Liberar todas as variaveis x[d, s, h] associadas aos recursos escolhidos.
5. Fixar todas as demais variaveis x[d, s, h] no valor da solucao atual.
6. Resolver o subproblema com limite curto de tempo.
7. Se a solucao melhorar, atualizar a incumbente.
```

Esse procedimento permite controlar o tamanho do subproblema e evita liberar variaveis sem relacao entre si.

## 3. Funcao De Score Para Conectividade

Para decidir quais recursos devem ser adicionados a vizinhanca, precisamos definir uma funcao de score. Quanto maior o score entre um recurso candidato e o conjunto ja escolhido, maior a chance de esse recurso ser adicionado a vizinhanca.

Uma funcao de score nao precisa ser perfeita. Ela e uma heuristica para identificar recursos que provavelmente se afetam mutuamente.

Uma primeira funcao agregada poderia ser:

```text
score(d, R) =
    5 * mesma_fase(d, R)
  + 3 * mesmo_curso(d, R)
  + 3 * sobreposicao_ou_proximidade_de_horario(d, R)
  + 2 * salas_preferenciais_em_comum(d, R)
  + 1 * demanda_semelhante(d, R)
  + penalidade_atual(d)
```

Onde:

```text
d = disciplina candidata
R = conjunto de recursos ja escolhidos
```

Essa funcao favorece disciplinas da mesma fase, do mesmo curso, com horarios relacionados, com salas preferenciais parecidas, com demanda semelhante e que ja estejam causando custo na solucao atual.

## 4. Relacao Com As Vizinhancas Do Artigo

O artigo define tres vizinhancas principais: `Curricula`, `Courses` e `Assignments`. Elas nao se aplicam literalmente ao nosso problema, porque no artigo o problema envolve escolher periodo e sala para aulas, enquanto no nosso PAS os horarios ja estao pre-definidos. Mesmo assim, a logica das vizinhancas se adapta bem.

### 4.1 Curricula

No artigo, a vizinhanca `Curricula` libera variaveis associadas a curriculos que compartilham disciplinas. O objetivo e melhorar a compactacao dos horarios de grupos de estudantes.

No nosso caso, o conceito mais proximo de curriculo e:

```text
curso + fase
```

Portanto, uma adaptacao natural e criar vizinhancas por fase:

```text
liberar CC_1
liberar ADM_5
liberar MED_8
```

Essa vizinhanca e especialmente coerente com o nosso modelo, porque a funcao objetivo ja penaliza a dispersao de salas por fase e por curso.

Efeito esperado:

```text
- reduzir a quantidade de salas usadas por uma fase;
- aproximar salas usadas por estudantes da mesma fase;
- melhorar a alocacao para salas preferenciais daquele curso;
- reorganizar uma fase inteira sem perturbar o restante da solucao.
```

### 4.2 Courses

No artigo, a vizinhanca `Courses` escolhe disciplinas com numero semelhante de estudantes. A ideia e permitir trocas entre disciplinas que disputam salas de capacidade parecida.

No nosso caso, essa vizinhanca tambem faz sentido, pois as salas possuem capacidades e a restricao de capacidade e uma das restricoes duras do modelo.

Uma adaptacao seria selecionar disciplinas com demanda parecida:

```text
disciplinas com aproximadamente 30 alunos
disciplinas com aproximadamente 50 alunos
disciplinas com demanda entre 45 e 55 alunos
```

Tambem podemos combinar demanda com salas preferenciais:

```text
disciplinas com demanda parecida e salas preferenciais em comum
```

Efeito esperado:

```text
- permitir trocas entre disciplinas que cabem nas mesmas salas;
- reduzir uso de salas nao preferenciais;
- melhorar encaixes quando uma sala boa esta ocupada por outra disciplina parecida;
- gerar subproblemas menores que uma vizinhanca estrutural muito ampla.
```

### 4.3 Assignments

No artigo, a vizinhanca `Assignments` e dinamica. Ela olha para a solucao atual e libera as alocacoes que mais contribuem para a penalidade.

No nosso caso, essa talvez seja a vizinhanca mais importante para melhoria fina da solucao.

Podemos considerar como alocacoes problematicas:

```text
- disciplina nao alocada em algum horario;
- disciplina alocada em sala nao preferencial;
- disciplina que usa muitas salas diferentes;
- fase que ficou espalhada em muitas salas;
- curso que ficou espalhado em salas distantes;
- disciplina ou fase envolvida em custo alto de distancia;
- alocacao que forca outra disciplina a ficar em sala pior.
```

Efeito esperado:

```text
- atacar diretamente os pontos que aumentam o valor da funcao objetivo;
- melhorar a solucao de forma mais direcionada;
- evitar gastar tempo reotimizando partes da solucao que ja estao boas;
- complementar as vizinhancas estruturais por curso e fase.
```

## 5. Exemplos Com Dados Do Projeto

Usando apenas os dados de entrada de 2024.1, temos aproximadamente:

```text
46 salas
436 disciplinas ou agrupamentos de disciplinas
94.990 variaveis x[d, s, h]
```

Esses numeros ajudam a justificar por que resolver o modelo completo pode ser dificil e por que faz sentido trabalhar com subproblemas menores. Os exemplos de `Curricula` e `Courses` foram montados a partir dos dados de entrada `horarios_2024_1.xlsx`, `salas_2024_1.csv` e `salas_preferenciais_2024.1.xlsx`. O exemplo de `Assignments` usa uma solucao incumbente gerada com esses mesmos dados, usando `TimeLimit=300`, `MIPFocus=1` e `NoRelHeurTime=300`.

### Exemplo 1: Curricula Adaptada Como Curso + Fase

Para o nosso problema, a adaptacao principal da vizinhanca `Curricula` e `curso + fase`. Portanto, o exemplo mais fiel ao artigo e liberar uma fase especifica de um curso.

Se liberarmos apenas a primeira fase de Ciencia da Computacao:

```text
recurso: CC_1
disciplinas liberadas: 7
variaveis x liberadas: 1.610
percentual aproximado do modelo: 1,69%
```

As disciplinas dessa fase possuem salas preferenciais como:

```text
308-B
309-B
310-B
305-B
```

Assim, liberar `CC_1` permitiria que o solver reorganizasse a primeira fase de Ciencia da Computacao considerando esse conjunto de salas preferenciais, sem alterar a alocacao de todos os cursos.

Efeito esperado:

```text
- tentar evitar penalidade por sala nao preferencial;
- manter ou melhorar a concentracao da fase;
- testar se ha espaco em salas mais adequadas quando outras variaveis proximas tambem sao liberadas.
```

Um contraexemplo estrutural util e `ADM_1`. A primeira fase de Administracao tem 5 disciplinas, 21 horarios-disciplina e 966 variaveis `x`. Como esse grupo e menor que `CC_1`, ele geraria uma vizinhanca ainda mais controlada.

```text
recurso: ADM_1
disciplinas liberadas: 5
variaveis x liberadas: 966
```

Esse contraexemplo ajuda a mostrar que nem toda vizinhanca por fase tem o mesmo tamanho ou o mesmo potencial. Depois de obter uma solucao incumbente compativel, a decisao de liberar `ADM_1` deveria considerar se essa fase realmente esta dispersa ou em salas nao preferenciais.

### Exemplo 2: Courses Adaptada Como Demanda Semelhante

No artigo, `Courses` aproxima disciplinas que possuem numero semelhante de alunos, porque elas tendem a disputar salas de capacidade semelhante.

No nosso caso, um exemplo concreto e selecionar disciplinas de Administracao com 50 alunos e mesmas salas preferenciais.

```text
recurso inicial: GCS539_1
disciplina: ADMINISTRACAO DA PRODUCAO I
curso/fase: ADM_5
alunos: 50
salas preferenciais: 210-B, 209-B, 208-B, 207-B, 206-B
horarios-disciplina: 4
variaveis x da disciplina: 184
```

Pela logica de `Courses`, o algoritmo poderia adicionar disciplinas candidatas com demanda semelhante e preferencias parecidas, por exemplo:

```text
- GCS540_1, ADMINISTRACAO DE MARKETING, ADM_5, 50 alunos;
- GCS525_1, FUNDAMENTOS DO COOPERATIVISMO, ADM_1, 50 alunos;
- GCS530_1, CONTABILIDADE GERAL, ADM_3, 50 alunos;
- GEX210_1, ESTATISTICA BASICA, ADM_3, 50 alunos.
```

Variaveis liberadas para `GCS539_1` e `GCS540_1`:

```text
disciplinas liberadas: 2
horarios-disciplina: 8
variaveis x liberadas: 368
```

Se o tamanho desejado da vizinhanca for maior, o algoritmo adicionaria outras disciplinas de 50 alunos com salas preferenciais em comum ate atingir o limite.

Efeito esperado:

```text
- tentar encontrar combinacoes viaveis em salas preferenciais;
- trocar salas entre disciplinas que cabem nos mesmos tipos de sala;
- reduzir risco de penalidade por sala nao preferencial sem mexer em uma fase inteira.
```

### Exemplo 3: Assignments Adaptada Como Penalidade Atual

No artigo, `Assignments` e uma vizinhanca dinamica: ela olha para a solucao atual e escolhe alocacoes que mais contribuem para a penalidade.

No nosso caso, o exemplo `Assignments` deve ser calculado sobre uma solucao incumbente gerada com os mesmos dados 2024.1. Para obter esse exemplo, foi gerada uma solucao com:

```text
TimeLimit = 300
MIPFocus = 1
NoRelHeurTime = 300
objetivo encontrado = 186.294,0
horarios nao alocados = 0
atribuicoes com disciplina desconhecida = 0
```

Nessa solucao, a disciplina com maior penalidade proxy foi:

```text
disciplina: GSA018_1
nome: FUNDAMENTOS PARA O CUIDADO PROFISSIONAL II
curso/fase: ENF_5
alunos: 50
horarios-disciplina: 16
sala atual: 206-A
salas preferenciais: 309-A, 308-A, 307-A, 305-A
alocacoes nao preferenciais: 16
horarios nao alocados: 0
variaveis x da disciplina: 736
penalidade proxy: 2.400
```

Essa disciplina e uma boa candidata para `Assignments` porque todas as suas 16 alocacoes ficaram fora das salas preferenciais. A vizinhanca poderia liberar:

```text
- as variaveis x[d, s, h] da propria GSA018_1;
- disciplinas da mesma fase ENF_5;
- disciplinas que ocupam 309-A, 308-A, 307-A ou 305-A nos horarios relevantes;
- disciplinas com demanda semelhante que poderiam trocar de sala com ela.
```

Efeito esperado:

```text
- atacar diretamente penalidades altas da solucao atual;
- tentar mover disciplinas para salas preferenciais;
- permitir trocas locais apenas com disciplinas realmente relacionadas ao problema.
```

### Observacao: Curso Inteiro Como Vizinhanca Adicional

Liberar um curso inteiro nao e a traducao direta de nenhuma das tres vizinhancas do artigo. No nosso caso, `Curricula` deve ser entendida principalmente como `curso + fase`.

Ainda assim, `curso inteiro` pode ser uma vizinhanca estrutural adicional para movimentos maiores. Por exemplo:

```text
recurso: CC
disciplinas liberadas: 47
variaveis x liberadas: 10.534
percentual aproximado do modelo: 11,09%
```

Essa vizinhanca pode ser util quando varias fases do mesmo curso estao ruins ao mesmo tempo, mas deve ser tratada como uma generalizacao nossa, nao como a adaptacao principal de `Curricula`.

## 6. Tipos De Vizinhanca Recomendados

Para uma primeira implementacao, podemos trabalhar com quatro tipos. O tipo principal inspirado em `Curricula` e a vizinhanca por fase, isto e, `curso + fase`.

### 6.1 Vizinhanca Por Fase

Recurso:

```text
curso + fase
```

Variaveis liberadas:

```text
todas as variaveis x[d, s, h] das disciplinas daquela fase
```

Quando usar:

```text
- fases com muitas salas diferentes;
- fases com salas distantes;
- fases com muitas alocacoes fora das preferencias.
```

Essa e provavelmente a vizinhanca mais alinhada com o modelo atual.

### 6.2 Vizinhanca Estrutural Adicional Por Curso

Recurso:

```text
curso
```

Variaveis liberadas:

```text
todas as variaveis x[d, s, h] das disciplinas do curso
```

Quando usar:

```text
- cursos muito espalhados;
- cursos com muitas fases afetadas;
- momentos em que a busca precisa de movimentos maiores.
```

Como pode ser grande, deve ser usada com cuidado ou com tamanho adaptativo.

Observacao:

```text
Esta vizinhanca nao e a adaptacao direta de Curricula.
Ela e uma generalizacao nossa para movimentos maiores.
```

### 6.3 Vizinhanca Por Demanda E Preferencia

Recurso:

```text
grupo de disciplinas com numero semelhante de alunos
```

Variaveis liberadas:

```text
x[d, s, h] das disciplinas com demanda parecida
```

Quando usar:

```text
- muitas disciplinas disputando salas de 50 ou 55 lugares;
- necessidade de trocar salas entre disciplinas compativeis;
- penalidade por sala nao preferencial.
```

Essa vizinhanca e a adaptacao mais direta da vizinhanca `Courses` do artigo.

### 6.4 Vizinhanca Por Penalidade Atual

Recurso:

```text
disciplinas ou alocacoes problematicas na solucao atual
```

Variaveis liberadas:

```text
x[d, s, h] das disciplinas com maior contribuicao para o custo
```

Quando usar:

```text
- existe disciplina nao alocada;
- existe disciplina em sala nao preferencial;
- existe fase ou curso muito disperso;
- a busca esta fazendo poucas melhorias com vizinhancas estruturais.
```

Essa e a adaptacao da vizinhanca `Assignments` do artigo.

## 7. Controle Do Tamanho Da Vizinhanca

O tamanho da vizinhanca pode ser medido de duas formas:

```text
numero de disciplinas liberadas
numero de variaveis x[d, s, h] liberadas
```

Como cada disciplina pode ter varios horarios, medir pelo numero de variaveis `x` e mais preciso.

Uma estrategia inspirada no artigo e ajustar o tamanho conforme o `MIPGap` do subproblema:

```text
se MIPGap > MaxGap:
    subproblema dificil demais
    reduzir tamanho da vizinhanca

se MIPGap < MinGap:
    subproblema facil demais
    aumentar tamanho da vizinhanca
```

Parametros iniciais possiveis:

```text
MinGap = 0.01
MaxGap = 0.10
Decay = 0.10
tempo_por_subproblema = 10 a 60 segundos
```

Tambem e possivel manter um tamanho separado para cada tipo de vizinhanca:

```text
S_fase
S_curso
S_demanda
S_penalidade
```

Isso e importante porque uma vizinhanca por curso tende a ser mais dificil que uma vizinhanca por fase.

## 8. Como Explicar Para O Orientador

A proposta pode ser resumida da seguinte forma:

```text
Em vez de gerar vizinhos por movimentos simples, como trocar uma disciplina de sala,
pretendemos gerar vizinhancas grandes e estruturadas. Cada vizinhanca libera um
conjunto conectado de variaveis x[d, s, h], enquanto o restante da solucao permanece
fixo. O solver entao reotimiza apenas essa parte da solucao.
```

O ponto central e que a conectividade dos recursos evita vizinhancas aleatorias demais. A busca passa a explorar regioes que fazem sentido para o problema:

```text
- fases que deveriam ficar proximas;
- cursos que compartilham preferencias de salas;
- disciplinas com demandas semelhantes;
- alocacoes que estao causando penalidade.
```

Com isso, a abordagem fica alinhada ao artigo de 2018, mas adaptada ao nosso problema, em que os horarios ja estao definidos e a principal decisao e a escolha das salas.

## 9. Proposta De Experimento

Para avaliar essas vizinhancas, podemos comparar:

```text
1. PLI completo com limite de tempo.
2. LNS usando apenas vizinhanca por fase.
3. LNS usando apenas vizinhanca por demanda.
4. LNS usando apenas vizinhanca por penalidade.
5. LNS combinando fase, curso, demanda e penalidade.
```

Metricas recomendadas:

```text
- valor da funcao objetivo;
- quantidade de disciplinas nao alocadas;
- quantidade de alocacoes em salas nao preferenciais;
- quantidade media de salas por fase;
- distancia media entre salas de uma mesma fase;
- distancia media entre salas de um mesmo curso;
- tempo ate encontrar a melhor solucao;
- MIPGap medio dos subproblemas.
```

Hipotese esperada:

```text
As vizinhancas isoladas podem melhorar partes especificas da solucao,
mas a combinacao de vizinhancas deve ter melhor desempenho geral,
assim como observado no artigo.
```

## 10. Proximos Passos

Os proximos passos para transformar esta ideia em implementacao sao:

```text
1. Refatorar o solve.py para separar construcao do modelo, solucao e extracao da solucao.
2. Criar uma estrutura para armazenar a solucao incumbente x[d, s, h].
3. Criar funcoes que retornem X(recurso) para curso, fase, demanda e penalidade.
4. Implementar a fixacao das variaveis fora da vizinhanca.
5. Resolver cada subproblema com limite curto de tempo.
6. Atualizar a solucao apenas quando houver melhoria.
7. Registrar logs por iteracao para comparar as vizinhancas.
```

Uma primeira versao simples e defensavel seria:

```text
1. Gerar solucao inicial com o PLI atual por tempo limitado.
2. Usar vizinhancas por fase e por penalidade atual.
3. Escolher o tipo de vizinhanca aleatoriamente.
4. Usar tamanho fixo nas primeiras execucoes.
5. Depois adicionar tamanho adaptativo baseado no MIPGap.
```

Essa ordem reduz o risco de implementacao e permite apresentar resultados intermediarios de forma clara.

## 11. Especificacao Operacional Das Vizinhanças

Esta secao transforma as ideias anteriores em contratos de implementacao. A
intencao e deixar claro o que cada vizinhanca recebe, como ela escolhe
disciplinas e quais variaveis `x[d, s, h]` ficam livres.

### 11.1 Fase

Inspiracao:

```text
Adaptacao principal da vizinhanca Curricula do artigo.
```

Entrada:

```text
- curso;
- fase;
- solucao incumbente;
- tamanho maximo opcional em variaveis x.
```

Variaveis liberadas:

```text
x[d, s, h] para toda disciplina d tal que:
    disciplinas[d].curso == curso
    disciplinas[d].fase == fase
```

Variaveis fixadas:

```text
todos os demais x[d, s, h] no valor da solucao incumbente.
```

Prioridade:

```text
score_fase =
    150 * alocacoes_nao_preferenciais
  + 2000 * horarios_nao_alocados
  + 25 * max(0, salas_usadas_qtd - 1)
```

Quando usar:

```text
- uma fase esta usando muitas salas;
- uma fase esta alocada longe das salas preferenciais;
- uma fase tem disciplinas nao alocadas;
- queremos uma vizinhanca pequena e estruturalmente coerente.
```

Risco:

```text
Pode nao melhorar quando o problema depende de trocar salas com disciplinas de
outros cursos ou fases que permanecem fixadas.
```

### 11.2 Penalidade Atual

Inspiracao:

```text
Adaptacao da vizinhanca Assignments do artigo.
```

Entrada:

```text
- solucao incumbente;
- numero maximo de disciplinas problematicas;
- pesos usados para estimar penalidade.
```

Variaveis liberadas:

```text
x[d, s, h] das disciplinas com maior penalidade proxy na solucao atual.
```

Penalidade proxy inicial:

```text
penalidade_disciplina =
    150 * alocacoes_em_sala_nao_preferencial
  + 2000 * horarios_nao_alocados
  + 250 * max(0, salas_usadas_qtd - 1)
```

Quando usar:

```text
- existe solucao incumbente salva;
- a busca precisa atacar diretamente os piores pontos;
- as vizinhancas por fase ou demanda melhoram pouco.
```

Risco:

```text
Se liberar apenas disciplinas ruins, o solver pode nao conseguir melhora porque
as disciplinas que ocupam as salas desejadas continuam fixas.
```

Extensao natural:

```text
Para cada disciplina problematica, liberar tambem:
- disciplinas da mesma fase;
- disciplinas com demanda semelhante;
- disciplinas que ocupam suas salas preferenciais nos mesmos horarios.
```

### 11.3 Demanda E Preferencia

Inspiracao:

```text
Adaptacao da vizinhanca Courses do artigo.
```

Entrada:

```text
- disciplina semente ou demanda alvo;
- tolerancia de alunos;
- solucao incumbente;
- tamanho maximo da vizinhanca.
```

Variaveis liberadas:

```text
x[d, s, h] das disciplinas com demanda semelhante.
```

Filtro recomendado:

```text
abs(alunos(d) - alunos(semente)) <= tolerancia
```

Score adicional:

```text
+2 se compartilha sala preferencial com a disciplina semente
+1 se pertence ao mesmo curso
+1 se possui horario no mesmo dia/turno
+penalidade_atual(d)
```

Quando usar:

```text
- varias disciplinas disputam salas de capacidade parecida;
- ha muitas penalidades por sala nao preferencial;
- queremos permitir trocas de sala entre disciplinas compativeis.
```

Risco:

```text
Pode gerar vizinhancas desconectadas se usar apenas demanda. Por isso, combinar
demanda com preferencias e penalidade atual tende a ser melhor.
```

### 11.4 Curso Inteiro

Inspiracao:

```text
Generalizacao propria do PAS; nao e a traducao direta de Curricula.
```

Entrada:

```text
- curso;
- solucao incumbente.
```

Variaveis liberadas:

```text
x[d, s, h] de todas as disciplinas do curso.
```

Quando usar:

```text
- varias fases do mesmo curso estao ruins;
- a busca ficou presa com vizinhancas menores;
- o limite de tempo por subproblema permite um movimento maior.
```

Risco:

```text
Pode gerar subproblemas grandes demais. Deve ser usada com menor frequencia ou
com tempo maior.
```

## 12. Ordem Recomendada De Implementacao

Para o estado atual do repositorio, a ordem mais segura e:

```text
1. Implementar parser de solucao .sol para recuperar x[d, s, h].
2. Implementar seletores puros de disciplinas:
   - por fase;
   - por curso;
   - por demanda;
   - por penalidade atual.
3. Implementar uma funcao que aplica:
   - Start = valor incumbente para todos os x;
   - LB = UB = valor incumbente para x fora da vizinhanca.
4. Adicionar parametros no solve.py para:
   - receber uma solucao incumbente;
   - receber uma lista de disciplinas liberadas;
   - resolver o subproblema com TimeLimit curto.
5. Criar um script de loop LNS que chama o solve.py varias vezes.
```

O primeiro prototipo deve usar apenas `fase` e `penalidade_atual`, porque essas
duas vizinhancas cobrem uma estrategia estrutural e uma estrategia reativa.
