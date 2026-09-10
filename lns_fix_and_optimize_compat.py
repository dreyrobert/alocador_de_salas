"""Compatibilidade para fluxos legados de LNS usados por `solve.py`.

O fluxo principal de fix-and-optimize por cursos trabalha com incumbentes em
memoria e prepara vizinhancas sobre um modelo ja construido. As funcoes aqui
mantem caminhos antigos do CLI de `solve.py`, como construir o modelo ja com
uma fase/curso livre e uma solucao incumbente aplicada.
"""

from __future__ import annotations

from typing import Iterable

from lns_fix_and_optimize import SolucaoX, preparar_fixacao_vizinhanca_x


def disciplinas_da_fase(disciplinas, curso: str, fase: int | str) -> set[str]:
    fase_int = int(fase)
    return {
        disciplina
        for disciplina, dados_disciplina in disciplinas.items()
        if dados_disciplina.curso == curso and int(dados_disciplina.fase) == fase_int
    }


def aplicar_start_e_fixacao_x(
    x_vars,
    solucao_x: SolucaoX,
    disciplinas_liberadas: Iterable[str],
) -> dict[str, int]:
    """Aplica MIP start e fixa x fora da vizinhanca em um modelo recem-criado."""
    _, resumo = preparar_fixacao_vizinhanca_x(x_vars, solucao_x, disciplinas_liberadas)

    return {
        "variaveis_x_total": resumo["variaveis_x_total"],
        "variaveis_x_livres": resumo["variaveis_x_livres"],
        "variaveis_x_fixadas": resumo["variaveis_x_fixadas"],
        "valores_start_definidos": resumo["valores_start_definidos"],
        "chaves_sem_valor_incumbente": resumo["chaves_sem_valor_incumbente"],
    }
