# Integração de `temp` em `heuristics`

Análise em 02/11/2026, com `origin/temp` em `af98f63` e `heuristics`
em `c1a4088`. O ancestral comum é o próprio `c1a4088`: o professor fez
um commit sobre a versão atual de `heuristics`.

## Alterações do professor

- `data/extrai_horarios_aula.py`: amplia cursos/fases, usa `num_turma`,
  verifica identificadores repetidos e atualiza o representante de agrupamentos.
- `domain/disciplina.py`: acrescenta abreviações de cursos e categorias.

São incluídos ECV, FUS, PIN, PROI, CE, PECG e EEI. Há também o nome
completo de Letras na tabela de abreviações.

## Evidência nas bases locais

As cinco bases de `2022_1` a `2024_1` não possuem `num_turma`.
As cinco de `2024_2` a `2026_2` possuem a coluna, com valores inteiros,
sem células vazias e sem duplicatas de `(cod, num_turma)`.

| Semestre | Linhas | IDs diferentes do contador artificial atual |
| --- | ---: | ---: |
| 2024_2 | 455 | 66 |
| 2025_1 | 503 | 62 |
| 2025_2 | 481 | 35 |
| 2026_1 | 514 | 34 |
| 2026_2 | 484 | 19 |

Assim, a mudança de identificação é efetiva. Soluções anteriores desses
semestres não devem ser reutilizadas como início sem verificar a correspondência
das turmas; uma chave igual pode passar a representar outra turma.

O carregamento das cinco bases novas foi verificado antes desta integração.
Isso não valida a formulação: `solve.py` cria variáveis e vínculos de cursos/fases
a partir das listas da instância. As vizinhanças que usam `instancia.cursos`
também dependem dessas listas. Novos cursos precisam constar nelas e ter
abreviações consistentes com `Disciplina.curso`.

## Sequência proposta

1. Incorporar os cursos e as abreviações do professor, verificando cobertura
   dos cursos e fases realmente presentes nas dez bases.
2. Usar `num_turma` quando a coluna existir; manter o contador histórico por
   código somente quando a coluna não existir. Se a coluna existir com valores
   vazios ou inválidos, informar o problema, sem inventar identificadores.
3. Validar unicidade antes do agrupamento, usando um conjunto de IDs lidos.
   Consultar apenas `disciplinas` não detecta uma turma repetida que já tenha
   virado filha de um agrupamento. Normalizar inteiros para evitar sufixos `.0`.
4. Conciliar a correção local do representante com a de `temp`, sem aplicar as
   duas em sequência. Testar substituições sucessivas, preservação dos filhos
   anteriores e ausência de referências a representantes removidos. O trecho
   atual também merece um teste com três disciplinas no mesmo agrupamento.
5. Verificar a criação de fases: a linha após o laço usa a variável residual
   `curso`, embora construa uma fase de Medicina. Ao ampliar a lista, essa chave
   muda de `PED_12` para `EEI_12`; corrigir para a chave explícita `MED_12` e
   verificar a cobertura das demais fases de Medicina nas bases reais.
6. Documentar a coluna opcional em `dados/README.md` e a incompatibilidade de
   identidade com soluções antigas nas bases novas.

## Verificações para concluir a integração

- Testes de coluna ausente, turma informada, valor inválido e duplicata,
  incluindo duplicata já absorvida por agrupamento.
- Testes de agrupamento com troca de representante e três ou mais disciplinas.
- Carregar as dez bases e conferir IDs, cobertura de cursos/fases e conservação
  das linhas de entrada entre representantes e filhos.
- Conferir que as vizinhanças por curso incluem os novos cursos.
- Executar a suíte existente; depois verificar construção do modelo e uma
  execução curta separada dos resultados experimentais, se necessária.
  Otimizações longas ficam para uma bateria posterior.

## Estado da implementação

As adaptações foram aplicadas localmente em `heuristics`, sem merge, commit ou
push. Foram incorporados os cursos/abreviações de `temp`, o uso de `num_turma`
com fallback somente para coluna ausente e validação independente de duplicatas.
As fases `MED_11` e `MED_12` agora usam o curso `MED`.

O agrupamento preserva os filhos na troca de representante e verifica a
sobreposição de datas com todos os membros. A comparação de horários passou a
comparar dia, turno e faixa em vez de procurar uma string dentro da outra.
Essas correções alteram agrupamentos e, portanto, podem alterar os resultados
mesmo nas bases antigas; comparações experimentais precisam usar a mesma versão.

Validação: 101 testes passaram. As dez bases foram carregadas com verificação de
conservação de todas as linhas entre representantes e filhos, unicidade dos IDs,
correspondência exata com `num_turma` quando presente, cobertura de cursos/fases
para todos os membros e cobertura dos representantes nas vizinhanças por curso.
Não houve construção de modelos completos nem execução de otimizações nesta etapa.
