
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
uv run alocador-salas-fixopt --tipo-vizinhanca dia_turno
uv run alocador-salas-fixopt --tipo-vizinhanca hibrida
```

No modo hibrido, a busca explora cursos ate uma passada sem melhoria, tenta as
vizinhancas por dia e turno e volta aos cursos se encontrar uma nova incumbente.
