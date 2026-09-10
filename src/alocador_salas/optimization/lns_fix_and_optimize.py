"""Utilitarios para LNS com fix-and-optimize no PAS.

As funcoes deste modulo evitam depender diretamente do Gurobi sempre que
possivel. Isso facilita testar a logica de vizinhancas e deixa o `solve.py`
responsavel apenas por construir e resolver o modelo.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


XKey = tuple[str, str, str]
SolucaoX = dict[XKey, int]


X_SOL_RE = re.compile(
    r"^x\[(?P<disciplina>[^,]+),(?P<sala>[^,]+),(?P<horario>[^\]]+)\]\s+"
    r"(?P<valor>[-0-9.]+)"
)
OBJETIVO_SOL_RE = re.compile(r"^# Objective value = (?P<objetivo>[-+0-9.eE]+)")


@dataclass(frozen=True)
class Vizinhanca:
    tipo: str
    recurso: str
    disciplinas_liberadas: frozenset[str]
    justificativa: str = ""


def parse_solucao_x(caminho_solucao: str | Path) -> SolucaoX:
    """Le variaveis x[d,s,h] de um arquivo .sol gerado pelo Gurobi."""
    solucao: SolucaoX = {}

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


def extrair_solucao_x(x_vars) -> SolucaoX:
    """Extrai variaveis x[d,s,h] diretamente do modelo resolvido."""
    solucao: SolucaoX = {}

    for chave, variavel in x_vars.items():
        solucao[chave] = int(round(float(variavel.X)))

    return solucao


def salvar_solucao_x(
    solucao_x: SolucaoX,
    caminho_solucao: str | Path,
    objetivo: float | None = None,
) -> None:
    """Salva uma solucao x[d,s,h] em formato .sol simples e parseavel."""
    caminho = Path(caminho_solucao)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    linhas = []
    if objetivo is not None:
        linhas.append(f"# Objective value = {objetivo}")

    for disciplina, sala, horario in sorted(solucao_x):
        linhas.append(f"x[{disciplina},{sala},{horario}] {solucao_x[(disciplina, sala, horario)]}")

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def parse_objetivo_sol(caminho_solucao: str | Path) -> float | None:
    """Le o valor objetivo registrado no cabecalho de um arquivo .sol."""
    with Path(caminho_solucao).open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            resultado = OBJETIVO_SOL_RE.match(linha.strip())
            if resultado:
                return float(resultado.group("objetivo"))
    return None


def disciplinas_do_curso(disciplinas, curso: str) -> set[str]:
    return {
        disciplina
        for disciplina, dados_disciplina in disciplinas.items()
        if dados_disciplina.curso == curso
    }


def vizinhanca_por_curso(disciplinas, curso: str) -> Vizinhanca:
    liberadas = disciplinas_do_curso(disciplinas, curso)
    return Vizinhanca(
        tipo="curso",
        recurso=curso,
        disciplinas_liberadas=frozenset(liberadas),
        justificativa="Libera um curso inteiro para movimentos estruturais maiores.",
    )


def aplicar_start_x(x_vars, solucao_x: SolucaoX) -> dict[str, int]:
    """Aplica MIP start nas variaveis x usando a solucao incumbente."""
    resumo = {
        "variaveis_x_total": 0,
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

    return resumo


def fixar_fora_da_vizinhanca_x(
    x_vars,
    solucao_x: SolucaoX,
    disciplinas_liberadas: Iterable[str],
) -> tuple[set[XKey], dict[str, int]]:
    """Fixa variaveis x fora da vizinhanca e retorna as chaves fixadas."""
    liberadas = set(disciplinas_liberadas)
    chaves_fixadas: set[XKey] = set()
    resumo = {
        "variaveis_x_total": 0,
        "variaveis_x_livres": 0,
        "variaveis_x_fixadas": 0,
        "chaves_sem_valor_incumbente": 0,
    }

    for chave, variavel in x_vars.items():
        resumo["variaveis_x_total"] += 1
        valor = solucao_x.get(chave)
        if valor is None:
            valor = 0
            resumo["chaves_sem_valor_incumbente"] += 1

        if chave[0] in liberadas:
            resumo["variaveis_x_livres"] += 1
            continue

        variavel.LB = valor
        variavel.UB = valor
        chaves_fixadas.add(chave)
        resumo["variaveis_x_fixadas"] += 1

    return chaves_fixadas, resumo


def liberar_fixacoes_x(
    x_vars,
    chaves_fixadas: Iterable[XKey],
    lb_padrao: int = 0,
    ub_padrao: int = 1,
) -> int:
    """Libera fixacoes anteriores das variaveis x."""
    liberadas = 0
    for chave in chaves_fixadas:
        variavel = x_vars.get(chave)
        if variavel is None:
            continue

        variavel.LB = lb_padrao
        variavel.UB = ub_padrao
        liberadas += 1

    return liberadas


def preparar_fixacao_vizinhanca_x(
    x_vars,
    solucao_x: SolucaoX,
    disciplinas_liberadas: Iterable[str],
    chaves_fixadas_anteriores: Iterable[XKey] | None = None,
) -> tuple[set[XKey], dict[str, int]]:
    """Libera a fixacao anterior, aplica start e fixa a vizinhanca atual."""
    fixacoes_liberadas = liberar_fixacoes_x(
        x_vars,
        chaves_fixadas_anteriores or (),
    )
    resumo_start = aplicar_start_x(x_vars, solucao_x)
    chaves_fixadas, resumo_fixacao = fixar_fora_da_vizinhanca_x(
        x_vars,
        solucao_x,
        disciplinas_liberadas,
    )

    resumo = {
        "variaveis_x_total": resumo_start["variaveis_x_total"],
        "variaveis_x_livres": resumo_fixacao["variaveis_x_livres"],
        "variaveis_x_fixadas": resumo_fixacao["variaveis_x_fixadas"],
        "valores_start_definidos": resumo_start["valores_start_definidos"],
        "chaves_sem_valor_incumbente": resumo_start["chaves_sem_valor_incumbente"],
        "fixacoes_liberadas": fixacoes_liberadas,
    }
    return chaves_fixadas, resumo

def solucao_melhorou(atual: dict | None, candidata: dict | None) -> bool:
    """Retorna True se a candidata e viavel e reduz estritamente o objetivo."""
    if not candidata or not candidata.get("solucoes"):
        return False

    objetivo_candidato = candidata.get("objetivo")
    if objetivo_candidato is None:
        return False

    if not atual or not atual.get("solucoes") or atual.get("objetivo") is None:
        return True

    return objetivo_candidato < atual["objetivo"]


def cursos_da_instancia(instancia) -> list[str]:
    """Extrai os cursos da instancia em ordem deterministica."""
    cursos = instancia.cursos
    if isinstance(cursos, dict):
        return sorted(cursos.keys())
    return sorted(cursos)


def salvar_historico_csv(historico: list[dict], caminho_csv: str | Path) -> None:
    """Salva o historico da busca local em CSV."""
    caminho = Path(caminho_csv)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    campos: list[str] = []
    for registro in historico:
        for campo in registro:
            if campo not in campos:
                campos.append(campo)

    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(historico)
