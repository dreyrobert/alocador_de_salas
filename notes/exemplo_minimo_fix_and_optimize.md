# Exemplo Minimo De Fix-And-Optimize Baseado Em PLI

Este documento explica o exemplo implementado em
`scripts/estudo_fix_and_optimize_lot_sizing.py`. A ideia e ter um caso pequeno,
com codigo acessivel, para entender o mecanismo antes de aplicar a mesma logica
ao Problema de Alocacao de Salas (PAS).

## 1. Problema usado no exemplo

O exemplo usa um problema de dimensionamento de lotes capacitado com varios
itens e varios periodos.

Para cada item e periodo, o modelo decide:

```text
y[i, t] = 1 se o item i e produzido no periodo t
produce[i, t] = quantidade produzida do item i no periodo t
stock[i, t] = estoque do item i ao fim do periodo t
```

A variavel mais importante para entender o fix-and-optimize e a binaria
`y[i, t]`. Ela cumpre o mesmo papel estrutural que `x[d, s, h]` cumpre no PAS:

```text
lot sizing: y[item, periodo]
PAS:        x[disciplina, sala, horario]
```

Em ambos os casos, a heuristica fixa a maior parte das binarias no valor da
solucao atual e libera apenas um subconjunto para reotimizacao por PLI.

## 2. Modelo PLI do exemplo

O modelo minimiza:

```text
custo de setup
+ custo de producao
+ custo de estoque
```

Sujeito a:

```text
- so e possivel produzir se y[i, t] = 1;
- a producao total de cada periodo respeita a capacidade;
- a demanda de cada item precisa ser atendida ao longo do horizonte;
- estoques nao podem ser negativos.
```

No codigo, isso aparece principalmente nas funcoes:

```text
small_instance()
build_model(...)
solve_model(...)
```

## 3. Solucao inicial

A funcao `initial_solution` cria uma solucao inicial deliberadamente simples:

```text
fixar y[i, t] = 1 para todo item i e periodo t
```

Ou seja, todos os setups ficam permitidos. Essa solucao tende a ser viavel, mas
cara, porque paga muitos custos de setup.

Essa etapa e util didaticamente porque deixa claro que o fix-and-optimize nao
precisa comecar de uma solucao otima. Ele precisa de uma incumbente a melhorar.

## 4. Vizinhanças no exemplo

As vizinhancas sao janelas de periodos. Com `window_size = 2`, por exemplo, uma
vizinhança pode liberar:

```text
periodos {0, 1}
periodos {1, 2}
periodos {2, 3}
...
```

Para uma janela especifica, o subproblema e criado assim:

```text
para t fora da janela:
    fixar y[i, t] no valor da solucao incumbente

para t dentro da janela:
    deixar y[i, t] livre para o Gurobi decidir
```

O solver entao resolve um PLI menor, porque grande parte das binarias ja esta
fixada.

## 5. Ciclo fix-and-optimize

O ciclo implementado em `fix_and_optimize` e:

```text
1. comecar com uma solucao incumbente;
2. gerar janelas de periodos;
3. para cada janela:
   3.1. fixar as binarias fora da janela;
   3.2. usar a solucao atual como MIP start;
   3.3. resolver o subproblema com limite curto de tempo;
   3.4. aceitar a candidata se o objetivo melhorar;
4. repetir por algumas passadas ou parar se nao houver melhora.
```

Esse e exatamente o padrao que queremos levar ao PAS.

## 6. Traducao para o PAS

No PAS, a variavel principal e:

```text
x[d, s, h] = 1 se a disciplina d usa a sala s no horario h
```

A traducao direta do exemplo e:

```text
solucao atual:
    valores atuais de x[d, s, h]

vizinhança:
    conjunto de disciplinas, fases, cursos ou alocacoes problematicas

subproblema:
    fixar x[d, s, h] fora da vizinhanca
    liberar x[d, s, h] dentro da vizinhanca
    resolver com Gurobi por pouco tempo
```

Exemplo por fase:

```text
liberar todas as variaveis x[d, s, h] de CC_1
fixar todas as demais variaveis x[d, s, h]
resolver o subproblema
aceitar se o objetivo global melhorar
```

## 7. Por que esse exemplo e suficiente para estudar

O exemplo e pequeno, mas contem os pontos essenciais:

```text
- modelo PLI completo;
- solucao incumbente;
- escolha de uma vizinhanca;
- fixacao de binarias fora da vizinhanca;
- MIP start;
- limite de tempo por subproblema;
- criterio de aceitacao por melhoria.
```

Assim, ele serve como ponte entre a teoria do fix-and-optimize e a
implementacao no alocador de salas.
