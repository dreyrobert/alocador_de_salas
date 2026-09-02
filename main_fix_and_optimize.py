from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from solve import carregar_instancia, construir_modelo, resolver_modelo
from lns_fix_and_optimize import parse_solucao_x

ARQUIVO_HORARIOS_PADRAO = "./dados/horarios_2024_1.xlsx"
ARQUIVO_SALAS_PADRAO = "./dados/salas_2024_1.csv"
ARQUIVO_PREFERENCIAIS_PADRAO = "./dados/salas_preferenciais_2024.1.xlsx"
ARQUIVO_SOLUCAO_INICIAL_PADRAO = "./resultados/primeira_solucao_fix_and_optimize.sol"
ARQUIVO_SOLUCAO_CURSO_PADRAO = "./resultados/solucao_fix_and_optimize_curso.sol"


def parametros_primeira_solucao(
    tempo_modelo: float = 300,
    tempo_heuristica: float = 300,
) -> dict[str, float | int]:
    """Parametros Gurobi usados para buscar a primeira solucao."""
    return {
        "TimeLimit": tempo_modelo,
        "MIPFocus": 1,
        "NoRelHeurTime": tempo_heuristica,
    }


def parametros_subproblema(tempo_subproblema: float = 300) -> dict[str, float | int]:
    """Parametros Gurobi usados em uma reotimizacao local."""
    return {
        "TimeLimit": tempo_subproblema,
        "MIPFocus": 1,
    }


def gerar_primeira_solucao(
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_solucao: str = ARQUIVO_SOLUCAO_INICIAL_PADRAO,
    tempo_modelo: float = 300,
    tempo_heuristica: float = 300,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
) -> dict:
    """Gera a solucao inicial para a futura rotina fix-and-optimize.

    A solucao e salva em `arquivo_solucao` quando o Gurobi encontra ao menos uma
    incumbente. O retorno e o mesmo dicionario produzido por `solve.main`, com a
    chave `etapa` para identificar esta fase da matheuristica.
    """
    caminho_solucao = Path(arquivo_solucao)
    caminho_solucao.parent.mkdir(parents=True, exist_ok=True)

    instancia = carregar(
        arquivo_horarios,
        arquivo_salas,
        arquivo_salas_preferenciais,
    )
    modelo_alocacao = construir(instancia)
    resultado = resolver(
        modelo_alocacao,
        parametros_gurobi=parametros_primeira_solucao(
            tempo_modelo=tempo_modelo,
            tempo_heuristica=tempo_heuristica,
        ),
        arquivo_solucao=str(caminho_solucao),
    )
    resultado["etapa"] = "primeira_solucao"
    return resultado


def reotimizar_vizinhanca_curso(
    arquivo_solucao_incumbente: str,
    curso_livre: str,
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_solucao: str = ARQUIVO_SOLUCAO_CURSO_PADRAO,
    tempo_subproblema: float = 300,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
    ler_solucao: Callable = parse_solucao_x,
) -> dict:
    """Reotimiza uma vizinhanca liberando apenas as disciplinas de um curso."""
    if not curso_livre:
        raise ValueError("Informe o curso que ficara livre na vizinhanca.")

    caminho_solucao = Path(arquivo_solucao)
    caminho_solucao.parent.mkdir(parents=True, exist_ok=True)

    instancia = carregar(
        arquivo_horarios,
        arquivo_salas,
        arquivo_salas_preferenciais,
    )
    solucao_incumbente_x = ler_solucao(arquivo_solucao_incumbente)
    modelo_alocacao = construir(
        instancia,
        solucao_incumbente_x=solucao_incumbente_x,
        curso_livre=curso_livre,
    )
    resultado = resolver(
        modelo_alocacao,
        parametros_gurobi=parametros_subproblema(tempo_subproblema),
        arquivo_solucao=str(caminho_solucao),
    )
    resultado["etapa"] = "reotimizacao_curso"
    resultado["curso_livre"] = curso_livre
    return resultado


def main() -> dict:
    parser = argparse.ArgumentParser(
        description="Gera a primeira solucao para a heuristica fix-and-optimize."
    )
    parser.add_argument(
        "--etapa",
        choices=["primeira-solucao", "curso"],
        default="primeira-solucao",
    )
    parser.add_argument("--horarios", default=ARQUIVO_HORARIOS_PADRAO)
    parser.add_argument("--salas", default=ARQUIVO_SALAS_PADRAO)
    parser.add_argument("--preferenciais", default=ARQUIVO_PREFERENCIAIS_PADRAO)
    parser.add_argument("--salvar-solucao", default="")
    parser.add_argument("--solucao-incumbente", default="")
    parser.add_argument("--curso-livre", default="")
    parser.add_argument("--tempo-modelo", type=float, default=300)
    parser.add_argument("--tempo-heuristica", type=float, default=300)
    parser.add_argument("--tempo-subproblema", type=float, default=300)
    args = parser.parse_args()

    if args.etapa == "curso":
        resultado = reotimizar_vizinhanca_curso(
            arquivo_solucao_incumbente=args.solucao_incumbente,
            curso_livre=args.curso_livre,
            arquivo_horarios=args.horarios,
            arquivo_salas=args.salas,
            arquivo_salas_preferenciais=args.preferenciais,
            arquivo_solucao=args.salvar_solucao or ARQUIVO_SOLUCAO_CURSO_PADRAO,
            tempo_subproblema=args.tempo_subproblema,
        )
    else:
        resultado = gerar_primeira_solucao(
            arquivo_horarios=args.horarios,
            arquivo_salas=args.salas,
            arquivo_salas_preferenciais=args.preferenciais,
            arquivo_solucao=args.salvar_solucao or ARQUIVO_SOLUCAO_INICIAL_PADRAO,
            tempo_modelo=args.tempo_modelo,
            tempo_heuristica=args.tempo_heuristica,
        )
    print("RESULTADO_JSON=" + json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return resultado


if __name__ == "__main__":
    main()
