from __future__ import annotations

import argparse
import json
import random
import shutil
import time
from pathlib import Path
from typing import Callable, Iterable

from solve import (
    InstanciaAlocacao,
    carregar_instancia,
    construir_modelo,
    resolver_modelo,
)
from lns_fix_and_optimize import (
    Vizinhanca,
    cursos_da_instancia,
    parse_objetivo_sol,
    parse_solucao_x,
    salvar_historico_csv,
    solucao_melhorou,
    vizinhanca_por_curso,
)

ARQUIVO_HORARIOS_PADRAO = "./dados/horarios_2024_1.xlsx"
ARQUIVO_SALAS_PADRAO = "./dados/salas_2024_1.csv"
ARQUIVO_PREFERENCIAIS_PADRAO = "./dados/salas_preferenciais_2024.1.xlsx"
ARQUIVO_SOLUCAO_INICIAL_PADRAO = "./resultados/primeira_solucao_fix_and_optimize.sol"
ARQUIVO_SOLUCAO_CURSO_PADRAO = "./resultados/solucao_fix_and_optimize_curso.sol"
ARQUIVO_MELHOR_SOLUCAO_PADRAO = "./resultados/melhor_solucao_fix_and_optimize.sol"
ARQUIVO_HISTORICO_CSV_PADRAO = "./resultados/historico_fix_and_optimize.csv"
ARQUIVO_HISTORICO_JSON_PADRAO = "./resultados/historico_fix_and_optimize.json"
PASTA_CANDIDATOS_PADRAO = "./resultados/candidatos"


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
    """Gera a solucao inicial para a rotina fix-and-optimize."""
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


def reotimizar_subproblema(
    arquivo_solucao_incumbente: str | Path | dict,
    disciplinas_livres: Iterable[str] | Vizinhanca,
    tipo_vizinhanca: str = "",
    recurso: str = "",
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_solucao: str = ARQUIVO_SOLUCAO_CURSO_PADRAO,
    tempo_subproblema: float = 300,
    instancia: InstanciaAlocacao | None = None,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
    ler_solucao: Callable = parse_solucao_x,
) -> dict:
    """Reotimiza uma vizinhanca generica (motor base para qualquer vizinhanca)."""
    if isinstance(disciplinas_livres, Vizinhanca):
        tipo_vizinhanca = tipo_vizinhanca or disciplinas_livres.tipo
        recurso = recurso or disciplinas_livres.recurso
        disciplinas_liberadas = set(disciplinas_livres.disciplinas_liberadas)
    else:
        disciplinas_liberadas = set(disciplinas_livres)
        tipo_vizinhanca = tipo_vizinhanca or "personalizada"
        recurso = recurso or "personalizado"

    if not disciplinas_liberadas:
        raise ValueError("A vizinhanca deve conter ao menos uma disciplina liberada.")

    arquivo_solucao_str = None
    if arquivo_solucao:
        caminho_solucao = Path(arquivo_solucao)
        caminho_solucao.parent.mkdir(parents=True, exist_ok=True)
        arquivo_solucao_str = str(caminho_solucao)

    if instancia is None:
        instancia = carregar(
            arquivo_horarios,
            arquivo_salas,
            arquivo_salas_preferenciais,
        )

    if isinstance(arquivo_solucao_incumbente, dict):
        solucao_incumbente_x = arquivo_solucao_incumbente
    else:
        if not arquivo_solucao_incumbente:
            raise ValueError("Informe o caminho do arquivo de solucao incumbente.")
        solucao_incumbente_x = ler_solucao(arquivo_solucao_incumbente)

    modelo_alocacao = construir(
        instancia,
        solucao_incumbente_x=solucao_incumbente_x,
        disciplinas_livres=disciplinas_liberadas,
    )
    resultado = resolver(
        modelo_alocacao,
        parametros_gurobi=parametros_subproblema(tempo_subproblema),
        arquivo_solucao=arquivo_solucao_str,
    )
    resultado["etapa"] = "reotimizacao_subproblema"
    resultado["tipo_vizinhanca"] = tipo_vizinhanca
    resultado["recurso"] = recurso
    resultado["disciplinas_livres_qtd"] = len(disciplinas_liberadas)
    return resultado


def reotimizar_vizinhanca_curso(
    arquivo_solucao_incumbente: str | Path | dict,
    curso_livre: str,
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_solucao: str = ARQUIVO_SOLUCAO_CURSO_PADRAO,
    tempo_subproblema: float = 300,
    instancia: InstanciaAlocacao | None = None,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
    ler_solucao: Callable = parse_solucao_x,
) -> dict:
    """Reotimiza a vizinhanca liberando apenas as disciplinas de um curso."""
    if not curso_livre:
        raise ValueError("Informe o curso que ficara livre na vizinhanca.")

    if instancia is None:
        instancia = carregar(
            arquivo_horarios,
            arquivo_salas,
            arquivo_salas_preferenciais,
        )

    vizinhanca = vizinhanca_por_curso(instancia.disciplinas, curso_livre)
    resultado = reotimizar_subproblema(
        arquivo_solucao_incumbente=arquivo_solucao_incumbente,
        disciplinas_livres=vizinhanca,
        arquivo_solucao=arquivo_solucao,
        tempo_subproblema=tempo_subproblema,
        instancia=instancia,
        carregar=carregar,
        construir=construir,
        resolver=resolver,
        ler_solucao=ler_solucao,
    )
    resultado["etapa"] = "reotimizacao_curso"
    resultado["curso_livre"] = curso_livre
    return resultado


def executar_passada_por_cursos(
    arquivo_solucao_incumbente: str | Path,
    instancia: InstanciaAlocacao,
    cursos: list[str] | None = None,
    arquivo_melhor_solucao: str | Path = ARQUIVO_MELHOR_SOLUCAO_PADRAO,
    pasta_candidatos: str | Path = PASTA_CANDIDATOS_PADRAO,
    tempo_subproblema: float = 60,
    numero_passada: int = 1,
    objetivo_incumbente_inicial: float | None = None,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
    ler_solucao: Callable = parse_solucao_x,
) -> tuple[dict, list[dict]]:
    """Executa uma passada completa de fix-and-optimize sobre a lista de cursos."""
    caminho_incumbente = Path(arquivo_solucao_incumbente)
    caminho_melhor = Path(arquivo_melhor_solucao)
    caminho_melhor.parent.mkdir(parents=True, exist_ok=True)

    if caminho_incumbente.resolve() != caminho_melhor.resolve() and caminho_incumbente.exists():
        shutil.copyfile(caminho_incumbente, caminho_melhor)

    if objetivo_incumbente_inicial is None:
        objetivo_incumbente_inicial = parse_objetivo_sol(caminho_melhor)

    incumbente_atual = {
        "solucoes": 1 if objetivo_incumbente_inicial is not None else 0,
        "objetivo": objetivo_incumbente_inicial,
        "arquivo_solucao": str(caminho_melhor),
    }

    if cursos is None:
        cursos = cursos_da_instancia(instancia)

    pasta_cand = Path(pasta_candidatos)
    pasta_cand.mkdir(parents=True, exist_ok=True)

    solucao_x_atual = ler_solucao(caminho_melhor)
    historico_passada: list[dict] = []

    for idx, curso in enumerate(cursos, start=1):
        arquivo_candidato = pasta_cand / f"candidato_curso_{curso}.sol"
        t0 = time.time()

        obj_anterior = incumbente_atual.get("objetivo")
        resultado_candidato = reotimizar_vizinhanca_curso(
            arquivo_solucao_incumbente=solucao_x_atual,
            curso_livre=curso,
            arquivo_solucao=str(arquivo_candidato),
            tempo_subproblema=tempo_subproblema,
            instancia=instancia,
            construir=construir,
            resolver=resolver,
            ler_solucao=ler_solucao,
        )
        tempo_gasto = time.time() - t0

        melhorou = solucao_melhorou(incumbente_atual, resultado_candidato)
        if melhorou:
            if arquivo_candidato.exists():
                shutil.copyfile(arquivo_candidato, caminho_melhor)
                solucao_x_atual = ler_solucao(caminho_melhor)
            incumbente_atual = resultado_candidato
            incumbente_atual["arquivo_solucao"] = str(caminho_melhor)

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
        }
        historico_passada.append(registro)

    return incumbente_atual, historico_passada


def executar_fix_and_optimize_cursos(
    arquivo_horarios: str = ARQUIVO_HORARIOS_PADRAO,
    arquivo_salas: str = ARQUIVO_SALAS_PADRAO,
    arquivo_salas_preferenciais: str = ARQUIVO_PREFERENCIAIS_PADRAO,
    arquivo_solucao_incumbente: str = "",
    arquivo_melhor_solucao: str = ARQUIVO_MELHOR_SOLUCAO_PADRAO,
    arquivo_log_csv: str = ARQUIVO_HISTORICO_CSV_PADRAO,
    arquivo_log_json: str = ARQUIVO_HISTORICO_JSON_PADRAO,
    tempo_modelo_inicial: float = 300,
    tempo_heuristica_inicial: float = 300,
    tempo_subproblema: float = 60,
    tempo_total_maximo: float | None = None,
    max_passadas: int = 1,
    embaralhar_cursos: bool = False,
    carregar: Callable = carregar_instancia,
    construir: Callable = construir_modelo,
    resolver: Callable = resolver_modelo,
    ler_solucao: Callable = parse_solucao_x,
) -> dict:
    """Executa a rotina completa de fix-and-optimize iterando sobre os cursos."""
    t_inicio_total = time.time()

    instancia = carregar(
        arquivo_horarios,
        arquivo_salas,
        arquivo_salas_preferenciais,
    )

    caminho_incumbente = Path(arquivo_solucao_incumbente) if arquivo_solucao_incumbente else None
    if caminho_incumbente and caminho_incumbente.exists():
        solucao_base = str(caminho_incumbente)
        obj_inicial = parse_objetivo_sol(caminho_incumbente)
    else:
        resultado_inicial = gerar_primeira_solucao(
            arquivo_horarios=arquivo_horarios,
            arquivo_salas=arquivo_salas,
            arquivo_salas_preferenciais=arquivo_salas_preferenciais,
            arquivo_solucao=ARQUIVO_SOLUCAO_INICIAL_PADRAO,
            tempo_modelo=tempo_modelo_inicial,
            tempo_heuristica=tempo_heuristica_inicial,
            carregar=lambda *args: instancia,
            construir=construir,
            resolver=resolver,
        )
        solucao_base = resultado_inicial.get("arquivo_solucao", ARQUIVO_SOLUCAO_INICIAL_PADRAO)
        obj_inicial = resultado_inicial.get("objetivo")

    caminho_melhor = Path(arquivo_melhor_solucao)
    caminho_melhor.parent.mkdir(parents=True, exist_ok=True)
    if Path(solucao_base).exists():
        shutil.copyfile(solucao_base, caminho_melhor)

    cursos = cursos_da_instancia(instancia)
    historico_total: list[dict] = []
    incumbente_atual = {
        "solucoes": 1 if obj_inicial is not None else 0,
        "objetivo": obj_inicial,
        "arquivo_solucao": str(caminho_melhor),
    }

    passadas_feitas = 0
    melhorias_totais = 0

    for passada in range(1, max_passadas + 1):
        if tempo_total_maximo and (time.time() - t_inicio_total) >= tempo_total_maximo:
            break

        cursos_rodada = list(cursos)
        if embaralhar_cursos:
            random.shuffle(cursos_rodada)

        incumbente_passada, hist_passada = executar_passada_por_cursos(
            arquivo_solucao_incumbente=caminho_melhor,
            instancia=instancia,
            cursos=cursos_rodada,
            arquivo_melhor_solucao=caminho_melhor,
            tempo_subproblema=tempo_subproblema,
            numero_passada=passada,
            objetivo_incumbente_inicial=incumbente_atual.get("objetivo"),
            construir=construir,
            resolver=resolver,
            ler_solucao=ler_solucao,
        )

        melhorias_na_passada = sum(1 for reg in hist_passada if reg["melhorou"])
        melhorias_totais += melhorias_na_passada
        historico_total.extend(hist_passada)
        incumbente_atual = incumbente_passada
        passadas_feitas += 1

        if melhorias_na_passada == 0:
            # Otimo local alcancado com respeito a vizinhancas unicas por curso
            break

    if arquivo_log_csv:
        salvar_historico_csv(historico_total, arquivo_log_csv)

    if arquivo_log_json:
        caminho_json = Path(arquivo_log_json)
        caminho_json.parent.mkdir(parents=True, exist_ok=True)
        caminho_json.write_text(json.dumps(historico_total, indent=2, ensure_ascii=False), encoding="utf-8")

    tempo_total_exec = round(time.time() - t_inicio_total, 2)
    obj_final = incumbente_atual.get("objetivo")
    ganho_absoluto = (obj_inicial - obj_final) if (obj_inicial is not None and obj_final is not None) else 0.0

    return {
        "etapa": "fix_and_optimize_cursos",
        "status": "CONCLUIDO",
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
        description="Gera a primeira solucao ou reotimiza vizinhancas por curso para a heuristica fix-and-optimize."
    )
    parser.add_argument(
        "--etapa",
        choices=["primeira-solucao", "curso", "passada-cursos", "loop-cursos"],
        default="primeira-solucao",
    )
    parser.add_argument("--horarios", default=ARQUIVO_HORARIOS_PADRAO)
    parser.add_argument("--salas", default=ARQUIVO_SALAS_PADRAO)
    parser.add_argument("--preferenciais", default=ARQUIVO_PREFERENCIAIS_PADRAO)
    parser.add_argument("--salvar-solucao", default="")
    parser.add_argument("--solucao-incumbente", default="")
    parser.add_argument("--curso-livre", default="")
    parser.add_argument("--max-passadas", type=int, default=1)
    parser.add_argument("--embaralhar-cursos", action="store_true")
    parser.add_argument("--tempo-modelo", type=float, default=300)
    parser.add_argument("--tempo-heuristica", type=float, default=300)
    parser.add_argument("--tempo-subproblema", type=float, default=300)
    parser.add_argument("--tempo-total", type=float, default=None)
    parser.add_argument("--log-csv", default=ARQUIVO_HISTORICO_CSV_PADRAO)
    parser.add_argument("--log-json", default=ARQUIVO_HISTORICO_JSON_PADRAO)
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
    elif args.etapa in ("passada-cursos", "loop-cursos"):
        max_pass = 1 if args.etapa == "passada-cursos" else args.max_passadas
        resultado = executar_fix_and_optimize_cursos(
            arquivo_horarios=args.horarios,
            arquivo_salas=args.salas,
            arquivo_salas_preferenciais=args.preferenciais,
            arquivo_solucao_incumbente=args.solucao_incumbente,
            arquivo_melhor_solucao=args.salvar_solucao or ARQUIVO_MELHOR_SOLUCAO_PADRAO,
            arquivo_log_csv=args.log_csv,
            arquivo_log_json=args.log_json,
            tempo_modelo_inicial=args.tempo_modelo,
            tempo_heuristica_inicial=args.tempo_heuristica,
            tempo_subproblema=args.tempo_subproblema,
            tempo_total_maximo=args.tempo_total,
            max_passadas=max_pass,
            embaralhar_cursos=args.embaralhar_cursos,
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
