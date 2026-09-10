from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable

from solve import (
    InstanciaAlocacao,
    carregar_instancia,
    construir_modelo,
    liberar_fixacoes_modelo,
    preparar_modelo_para_vizinhanca,
    resolver_modelo,
)
from lns_fix_and_optimize import (
    SolucaoX,
    Vizinhanca,
    cursos_da_instancia,
    salvar_historico_csv,
    salvar_solucao_x,
    solucao_melhorou,
    vizinhanca_por_curso,
)

ARQUIVO_HORARIOS_PADRAO = "./dados/2024_1/horarios_2024_1.xlsx"
ARQUIVO_SALAS_PADRAO = "./dados/2024_1/salas_2024_1.csv"
ARQUIVO_PREFERENCIAIS_PADRAO = "./dados/2024_1/salas_preferenciais_2024.1.xlsx"
PASTA_FIX_AND_OPTIMIZE_PADRAO = "./resultados/fix_and_optimize"
ARQUIVO_MELHOR_SOLUCAO_PADRAO = f"{PASTA_FIX_AND_OPTIMIZE_PADRAO}/melhor_solucao_fix_and_optimize.sol"
ARQUIVO_HISTORICO_CSV_PADRAO = f"{PASTA_FIX_AND_OPTIMIZE_PADRAO}/historico_fix_and_optimize.csv"
ARQUIVO_HISTORICO_JSON_PADRAO = f"{PASTA_FIX_AND_OPTIMIZE_PADRAO}/historico_fix_and_optimize.json"
PASTA_CANDIDATOS_PADRAO = f"{PASTA_FIX_AND_OPTIMIZE_PADRAO}/candidatos"


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


def reotimizar_vizinhanca(
    modelo_alocacao,
    solucao_incumbente_x: SolucaoX,
    vizinhanca: Vizinhanca,
    tempo_subproblema: float,
    arquivo_solucao: str | None = None,
    preparar_modelo: Callable = preparar_modelo_para_vizinhanca,
    resolver: Callable = resolver_modelo,
) -> dict:
    """Reotimiza uma vizinhanca em um modelo ja construido."""
    disciplinas_liberadas = set(vizinhanca.disciplinas_liberadas)
    if not disciplinas_liberadas:
        raise ValueError("A vizinhanca deve conter ao menos uma disciplina liberada.")

    preparar_modelo(
        modelo_alocacao,
        solucao_incumbente_x=solucao_incumbente_x,
        disciplinas_livres=disciplinas_liberadas,
    )
    resultado = resolver(
        modelo_alocacao,
        parametros_gurobi=parametros_subproblema(tempo_subproblema),
        arquivo_solucao=arquivo_solucao,
    )
    resultado["etapa"] = "reotimizacao_vizinhanca"
    resultado["tipo_vizinhanca"] = vizinhanca.tipo
    resultado["recurso"] = vizinhanca.recurso
    resultado["disciplinas_livres_qtd"] = len(disciplinas_liberadas)
    return resultado


def executar_passada_por_cursos(
    solucao_incumbente_x: SolucaoX,
    instancia: InstanciaAlocacao,
    modelo_alocacao,
    cursos: list[str] | None = None,
    pasta_candidatos: str | Path = PASTA_CANDIDATOS_PADRAO,
    tempo_subproblema: float = 60,
    numero_passada: int = 1,
    objetivo_incumbente_inicial: float | None = None,
    preparar_modelo: Callable = preparar_modelo_para_vizinhanca,
    resolver: Callable = resolver_modelo,
    tempo_fim_total: float | None = None,
    salvar_candidatos: bool = False,
) -> tuple[dict, list[dict]]:
    """Executa uma passada completa de fix-and-optimize sobre a lista de cursos."""
    solucao_x_atual = solucao_incumbente_x
    incumbente_atual = {
        "solucoes": 1 if objetivo_incumbente_inicial is not None else 0,
        "objetivo": objetivo_incumbente_inicial,
        "arquivo_solucao": None,
        "solucao_x": solucao_x_atual,
    }

    if cursos is None:
        cursos = cursos_da_instancia(instancia)

    pasta_cand = Path(pasta_candidatos)
    if salvar_candidatos:
        pasta_cand.mkdir(parents=True, exist_ok=True)
    historico_passada: list[dict] = []

    for idx, curso in enumerate(cursos, start=1):
        tempo_subproblema_efetivo = tempo_subproblema
        if tempo_fim_total is not None:
            tempo_restante = tempo_fim_total - time.time()
            if tempo_restante <= 0:
                break
            tempo_subproblema_efetivo = min(tempo_subproblema, tempo_restante)

        arquivo_candidato = pasta_cand / f"candidato_curso_{curso}.sol"
        arquivo_candidato_str = str(arquivo_candidato) if salvar_candidatos else None
        t0 = time.time()

        obj_anterior = incumbente_atual.get("objetivo")
        vizinhanca = vizinhanca_por_curso(instancia.disciplinas, curso)
        if not vizinhanca.disciplinas_liberadas:
            continue

        resultado_candidato = reotimizar_vizinhanca(
            modelo_alocacao=modelo_alocacao,
            solucao_incumbente_x=solucao_x_atual,
            vizinhanca=vizinhanca,
            tempo_subproblema=tempo_subproblema_efetivo,
            arquivo_solucao=arquivo_candidato_str,
            preparar_modelo=preparar_modelo,
            resolver=resolver,
        )
        resultado_candidato["curso_livre"] = curso
        tempo_gasto = time.time() - t0

        melhorou = solucao_melhorou(incumbente_atual, resultado_candidato)
        if melhorou:
            solucao_candidata_x = resultado_candidato.get("solucao_x")
            if solucao_candidata_x is None:
                raise ValueError("Subproblema melhorou, mas nao retornou solucao_x em memoria.")

            solucao_x_atual = solucao_candidata_x
            incumbente_atual = resultado_candidato
            incumbente_atual["solucao_x"] = solucao_x_atual

        lns_info = resultado_candidato.get("lns") or {}
        registro = {
            "passada": numero_passada,
            "iteracao": idx,
            "vizinhanca": "curso",
            "curso": curso,
            "disciplinas_livres": resultado_candidato.get("disciplinas_livres_qtd", 0),
            "variaveis_x_livres": lns_info.get("variaveis_x_livres", 0),
            "variaveis_x_fixadas": lns_info.get("variaveis_x_fixadas", 0),
            "status_solver": resultado_candidato.get("status_nome", ""),
            "objetivo_anterior": obj_anterior,
            "objetivo_candidato": resultado_candidato.get("objetivo"),
            "melhorou": melhorou,
            "objetivo_incumbente": incumbente_atual.get("objetivo"),
            "tempo_gasto_s": round(tempo_gasto, 2),
            "tempo_limite_subproblema_s": round(tempo_subproblema_efetivo, 2),
        }
        historico_passada.append(registro)

    return incumbente_atual, historico_passada


def executar_fix_and_optimize_cursos(
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_melhor_solucao: str = ARQUIVO_MELHOR_SOLUCAO_PADRAO,
    arquivo_log_csv: str = ARQUIVO_HISTORICO_CSV_PADRAO,
    arquivo_log_json: str = ARQUIVO_HISTORICO_JSON_PADRAO,
    tempo_modelo_inicial: float = 300,
    tempo_heuristica_inicial: float = 300,
    tempo_subproblema: float = 60,
    tempo_total_maximo: float | None = None,
    apenas_uma_passada: bool = False,
    salvar_candidatos: bool = False,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    preparar_modelo: Callable = preparar_modelo_para_vizinhanca,
    liberar_modelo: Callable = liberar_fixacoes_modelo,
    resolver: Callable = resolver_modelo,
) -> dict:
    """Executa a rotina completa de fix-and-optimize iterando sobre os cursos."""
    t_inicio_total = time.time()
    tempo_fim_total = (
        t_inicio_total + tempo_total_maximo
        if tempo_total_maximo is not None
        else None
    )

    instancia = carregar(
        arquivo_horarios,
        arquivo_salas,
        arquivo_salas_preferenciais,
    )

    modelo_alocacao = construir(instancia)
    caminho_melhor = Path(arquivo_melhor_solucao)
    caminho_melhor.parent.mkdir(parents=True, exist_ok=True)
    historico_total: list[dict] = []
    passadas_feitas = 0
    melhorias_totais = 0
    status_execucao = "CONCLUIDO"
    obj_inicial = None
    obj_final = None
    solucao_final_x: SolucaoX | None = None

    try:
        resultado_inicial = resolver(
            modelo_alocacao,
            parametros_gurobi=parametros_primeira_solucao(
                tempo_modelo=tempo_modelo_inicial,
                tempo_heuristica=tempo_heuristica_inicial,
            ),
            arquivo_solucao=None,
        )
        resultado_inicial["etapa"] = "primeira_solucao"
        obj_inicial = resultado_inicial.get("objetivo")
        solucao_x_atual: SolucaoX | None = resultado_inicial.get("solucao_x")

        incumbente_atual = {
            "solucoes": 1 if obj_inicial is not None else 0,
            "objetivo": obj_inicial,
            "arquivo_solucao": str(caminho_melhor),
            "solucao_x": solucao_x_atual,
        }

        if solucao_x_atual is None:
            status_execucao = "SEM_SOLUCAO_INICIAL"
        else:
            cursos = cursos_da_instancia(instancia)
            passada = 1

            while incumbente_atual.get("solucao_x") is not None:
                if tempo_total_maximo and (time.time() - t_inicio_total) >= tempo_total_maximo:
                    break

                cursos_rodada = list(cursos)

                incumbente_passada, hist_passada = executar_passada_por_cursos(
                    solucao_incumbente_x=incumbente_atual["solucao_x"],
                    instancia=instancia,
                    modelo_alocacao=modelo_alocacao,
                    cursos=cursos_rodada,
                    tempo_subproblema=tempo_subproblema,
                    numero_passada=passada,
                    objetivo_incumbente_inicial=incumbente_atual.get("objetivo"),
                    preparar_modelo=preparar_modelo,
                    resolver=resolver,
                    tempo_fim_total=tempo_fim_total,
                    salvar_candidatos=salvar_candidatos,
                )

                melhorias_na_passada = sum(1 for reg in hist_passada if reg["melhorou"])
                melhorias_totais += melhorias_na_passada
                historico_total.extend(hist_passada)
                incumbente_atual = incumbente_passada
                passadas_feitas += 1

                if apenas_uma_passada:
                    break

                if melhorias_na_passada == 0:
                    # Otimo local alcancado com respeito a vizinhancas unicas por curso
                    break
                passada += 1

        obj_final = incumbente_atual.get("objetivo")
        solucao_final_x = incumbente_atual.get("solucao_x")
        if arquivo_melhor_solucao and solucao_final_x is not None:
            salvar_solucao_x(solucao_final_x, caminho_melhor, obj_final)
    finally:
        liberar_modelo(modelo_alocacao)

    if arquivo_log_csv:
        salvar_historico_csv(historico_total, arquivo_log_csv)

    if arquivo_log_json:
        caminho_json = Path(arquivo_log_json)
        caminho_json.parent.mkdir(parents=True, exist_ok=True)
        caminho_json.write_text(json.dumps(historico_total, indent=2, ensure_ascii=False), encoding="utf-8")

    tempo_total_exec = round(time.time() - t_inicio_total, 2)
    ganho_absoluto = (obj_inicial - obj_final) if (obj_inicial is not None and obj_final is not None) else 0.0

    return {
        "etapa": "fix_and_optimize_cursos",
        "status": status_execucao,
        "objetivo_inicial": obj_inicial,
        "objetivo_final": obj_final,
        "ganho_absoluto": ganho_absoluto,
        "passadas_executadas": passadas_feitas,
        "total_iteracoes": len(historico_total),
        "melhorias_aceitas": melhorias_totais,
        "tempo_total_s": tempo_total_exec,
        "arquivo_melhor_solucao": str(caminho_melhor),
        "arquivo_log_csv": arquivo_log_csv,
        "arquivo_log_json": arquivo_log_json,
        "historico": historico_total,
    }


def main() -> dict:
    parser = argparse.ArgumentParser(
        description="Executa a heuristica fix-and-optimize por cursos."
    )
    parser.add_argument("--horarios", default=ARQUIVO_HORARIOS_PADRAO)
    parser.add_argument("--salas", default=ARQUIVO_SALAS_PADRAO)
    parser.add_argument("--preferenciais", default=ARQUIVO_PREFERENCIAIS_PADRAO)
    parser.add_argument("--salvar-solucao", default="")
    parser.add_argument("--tempo-modelo", type=float, default=300)
    parser.add_argument("--tempo-heuristica", type=float, default=300)
    parser.add_argument("--tempo-subproblema", type=float, default=300)
    parser.add_argument("--tempo-total", type=float, default=None)
    parser.add_argument("--apenas-uma-passada", action="store_true")
    parser.add_argument("--log-csv", default=ARQUIVO_HISTORICO_CSV_PADRAO)
    parser.add_argument("--log-json", default=ARQUIVO_HISTORICO_JSON_PADRAO)
    parser.add_argument(
        "--salvar-candidatos",
        action="store_true",
        help="Salva solucoes candidatas por curso para debug. Por padrao, candidatos ficam apenas em memoria.",
    )
    args = parser.parse_args()

    resultado = executar_fix_and_optimize_cursos(
        arquivo_horarios=args.horarios,
        arquivo_salas=args.salas,
        arquivo_salas_preferenciais=args.preferenciais,
        arquivo_melhor_solucao=args.salvar_solucao or ARQUIVO_MELHOR_SOLUCAO_PADRAO,
        arquivo_log_csv=args.log_csv,
        arquivo_log_json=args.log_json,
        tempo_modelo_inicial=args.tempo_modelo,
        tempo_heuristica_inicial=args.tempo_heuristica,
        tempo_subproblema=args.tempo_subproblema,
        tempo_total_maximo=args.tempo_total,
        apenas_uma_passada=args.apenas_uma_passada,
        salvar_candidatos=args.salvar_candidatos,
    )
    print("RESULTADO_JSON=" + json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    return resultado


if __name__ == "__main__":
    main()
