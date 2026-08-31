"""Utilitarios para LNS com fix-and-optimize no PAS.

As funcoes deste modulo evitam depender diretamente do Gurobi sempre que
possivel. Isso facilita testar a logica de vizinhancas e deixa o `solve.py`
responsavel apenas por construir e resolver o modelo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


XKey = tuple[str, str, str]


X_SOL_RE = re.compile(
    r"^x\[(?P<disciplina>[^,]+),(?P<sala>[^,]+),(?P<horario>[^\]]+)\]\s+"
    r"(?P<valor>[-0-9.]+)"
)


@dataclass(frozen=True)
class Vizinhanca:
    tipo: str
    recurso: str
    disciplinas_liberadas: frozenset[str]
    justificativa: str = ""

    @property
    def disciplinas(self) -> set[str]:
        return set(self.disciplinas_liberadas)


def parse_solucao_x(caminho_solucao: str | Path) -> dict[XKey, int]:
    """Le variaveis x[d,s,h] de um arquivo .sol gerado pelo Gurobi."""
    solucao: dict[XKey, int] = {}

    with Path(caminho_solucao).open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            resultado = X_SOL_RE.match(linha.strip())
            if not resultado:
                continue

            chave = (
                resultado.group("disciplina"),
                resultado.group("sala"),
                resultado.group("horario"),
            )
            solucao[chave] = int(round(float(resultado.group("valor"))))

    return solucao


def alocacoes_por_disciplina_horario(solucao_x: dict[XKey, int]) -> dict[tuple[str, str], str]:
    """Converte valores x em atribuicoes (disciplina, horario) -> sala."""
    alocacoes = {}
    for (disciplina, sala, horario), valor in solucao_x.items():
        if valor == 1:
            alocacoes[(disciplina, horario)] = sala
    return alocacoes


def disciplinas_da_fase(disciplinas, curso: str, fase: int | str) -> set[str]:
    fase_int = int(fase)
    return {
        disciplina
        for disciplina, dados_disciplina in disciplinas.items()
        if dados_disciplina.curso == curso and int(dados_disciplina.fase) == fase_int
    }


def disciplinas_do_curso(disciplinas, curso: str) -> set[str]:
    return {
        disciplina
        for disciplina, dados_disciplina in disciplinas.items()
        if dados_disciplina.curso == curso
    }


def disciplinas_por_demanda(
    disciplinas,
    demanda_alvo: int,
    tolerancia: int = 5,
) -> set[str]:
    return {
        disciplina
        for disciplina, dados_disciplina in disciplinas.items()
        if abs(dados_disciplina.max_alunos_agrupamento() - demanda_alvo) <= tolerancia
    }


def vizinhanca_por_fase(disciplinas, curso: str, fase: int | str) -> Vizinhanca:
    liberadas = disciplinas_da_fase(disciplinas, curso, fase)
    return Vizinhanca(
        tipo="fase",
        recurso=f"{curso}_{int(fase)}",
        disciplinas_liberadas=frozenset(liberadas),
        justificativa="Libera disciplinas de uma mesma fase para reduzir dispersao e preferenciais ruins.",
    )


def vizinhanca_por_curso(disciplinas, curso: str) -> Vizinhanca:
    liberadas = disciplinas_do_curso(disciplinas, curso)
    return Vizinhanca(
        tipo="curso",
        recurso=curso,
        disciplinas_liberadas=frozenset(liberadas),
        justificativa="Libera um curso inteiro para movimentos estruturais maiores.",
    )


def vizinhanca_por_demanda(
    disciplinas,
    demanda_alvo: int,
    tolerancia: int = 5,
) -> Vizinhanca:
    liberadas = disciplinas_por_demanda(disciplinas, demanda_alvo, tolerancia)
    return Vizinhanca(
        tipo="demanda",
        recurso=f"demanda_{demanda_alvo}_tol_{tolerancia}",
        disciplinas_liberadas=frozenset(liberadas),
        justificativa="Libera disciplinas que tendem a disputar salas de capacidade semelhante.",
    )


def pontuar_disciplinas_por_penalidade(
    disciplinas,
    solucao_x: dict[XKey, int],
    peso_sala_nao_preferencial: int = 150,
    peso_nao_alocada: int = 2000,
    peso_multiplas_salas: int = 250,
) -> list[dict]:
    alocacoes = alocacoes_por_disciplina_horario(solucao_x)
    linhas = []

    for disciplina, dados_disciplina in disciplinas.items():
        salas_usadas = set()
        nao_preferenciais = 0
        nao_alocadas = 0

        for horario in dados_disciplina.horarios_agrupamento():
            sala = alocacoes.get((disciplina, horario))
            if sala is None:
                nao_alocadas += 1
                continue

            salas_usadas.add(sala)
            if dados_disciplina.salasPreferenciais and sala not in dados_disciplina.salasPreferenciais:
                nao_preferenciais += 1

        penalidade = (
            peso_sala_nao_preferencial * nao_preferenciais
            + peso_nao_alocada * nao_alocadas
            + peso_multiplas_salas * max(0, len(salas_usadas) - 1)
        )
        linhas.append(
            {
                "disciplina": disciplina,
                "curso": dados_disciplina.curso,
                "fase": dados_disciplina.fase,
                "salas_usadas_qtd": len(salas_usadas),
                "alocacoes_nao_preferenciais": nao_preferenciais,
                "horarios_nao_alocados": nao_alocadas,
                "penalidade_proxy": penalidade,
            }
        )

    return sorted(linhas, key=lambda linha: linha["penalidade_proxy"], reverse=True)


def vizinhanca_por_penalidade_atual(
    disciplinas,
    solucao_x: dict[XKey, int],
    top_n: int = 10,
) -> Vizinhanca:
    ranking = pontuar_disciplinas_por_penalidade(disciplinas, solucao_x)
    liberadas = [
        linha["disciplina"]
        for linha in ranking
        if linha["penalidade_proxy"] > 0
    ][:top_n]
    return Vizinhanca(
        tipo="penalidade_atual",
        recurso=f"top_{top_n}_disciplinas_problematicas",
        disciplinas_liberadas=frozenset(liberadas),
        justificativa="Libera as disciplinas que mais contribuem para a penalidade da solucao atual.",
    )


def chaves_livres_por_disciplinas(
    chaves_x: Iterable[XKey],
    disciplinas_liberadas: Iterable[str],
) -> set[XKey]:
    liberadas = set(disciplinas_liberadas)
    return {chave for chave in chaves_x if chave[0] in liberadas}


def aplicar_start_e_fixacao_x(
    x_vars,
    solucao_x: dict[XKey, int],
    disciplinas_liberadas: Iterable[str],
) -> dict[str, int]:
    """Aplica MIP start em todos os x e fixa os x fora da vizinhanca.

    `x_vars` deve ser um dicionario no formato usado pelo `solve.py`:
    `(disciplina, sala, horario) -> variavel Gurobi`.
    """
    liberadas = set(disciplinas_liberadas)
    resumo = {
        "variaveis_x_total": 0,
        "variaveis_x_livres": 0,
        "variaveis_x_fixadas": 0,
        "valores_start_definidos": 0,
        "chaves_sem_valor_incumbente": 0,
    }

    for chave, variavel in x_vars.items():
        resumo["variaveis_x_total"] += 1
        valor = solucao_x.get(chave)
        if valor is None:
            valor = 0
            resumo["chaves_sem_valor_incumbente"] += 1

        variavel.Start = valor
        resumo["valores_start_definidos"] += 1

        if chave[0] in liberadas:
            resumo["variaveis_x_livres"] += 1
            continue

        variavel.LB = valor
        variavel.UB = valor
        resumo["variaveis_x_fixadas"] += 1

    return resumo
