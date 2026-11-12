from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_fixopt_semestre import caminhos_entrada, escrever_resumos
from alocador_salas.optimization.solve import main as resolver_pli


def tempo_positivo(valor: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero) or numero <= 0:
        raise argparse.ArgumentTypeError("O tempo deve ser finito e maior que zero.")
    return numero


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roda o PLI dos semestres selecionados em sequencia, sem Fix-and-Optimize.")
    parser.add_argument("--semestre", required=True, nargs="+", action="extend",
                        help="Ex.: --semestre 2024_1 2024_2. Pode repetir a opcao.")
    parser.add_argument("--raiz-dados", default="dados")
    parser.add_argument("--saida", default="resultados/experimentos")
    parser.add_argument("--horarios")
    parser.add_argument("--salas")
    parser.add_argument("--preferenciais")
    parser.add_argument("--tempo-total", type=tempo_positivo, default=14400,
                        help="TimeLimit do Gurobi em segundos (padrao: 14400, 4 horas).")
    parser.add_argument("--mipfocus", type=int, choices=range(4), default=0)
    parser.add_argument("--tempo-heuristica", type=tempo_positivo, default=None,
                        help="NoRelHeurTime em segundos; se omitido, usa o padrao do Gurobi (0).")
    parser.add_argument("--seed", type=int, default=0, help="Seed do Gurobi (padrao: 0).")
    parser.add_argument("--pular-existentes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    semestres = list(dict.fromkeys(args.semestre))
    if len(semestres) > 1 and any((args.horarios, args.salas, args.preferenciais)):
        parser.error("--horarios, --salas e --preferenciais exigem um unico semestre; "
                     "para varios, use --raiz-dados com a estrutura por semestre.")
    planos = []
    for semestre in semestres:
        entradas = caminhos_entrada(semestre, args.raiz_dados, args.horarios,
                                   args.salas, args.preferenciais)
        pasta = Path(args.saida) / semestre / "pli" / "modelo_completo"
        planos.append({
            "semestre": semestre,
            "entradas": {nome: str(caminho) for nome, caminho in entradas.items()},
            "pasta_saida": str(pasta),
            "parametros_gurobi": {
                "TimeLimit": args.tempo_total,
                "MIPFocus": args.mipfocus,
                "NoRelHeurTime": args.tempo_heuristica or 0,
                "Seed": args.seed,
                "LogFile": str(pasta / "gurobi.log"),
            },
        })
    if args.dry_run:
        print(json.dumps(planos[0] if len(planos) == 1 else {"experimentos": planos},
                         indent=2, ensure_ascii=False))
        return 0

    # Confere toda a bateria antes de iniciar qualquer execucao longa.
    pendentes = []
    for plano in planos:
        pasta = Path(plano["pasta_saida"])
        if (pasta / "resumo.json").exists() and args.pular_existentes:
            anterior = json.loads((pasta / "resumo.json").read_text(encoding="utf-8"))
            if anterior and anterior[0].get("status_execucao_script") == "CONCLUIDO":
                print(f"[PULADO] PLI {plano['semestre']}: {pasta}")
                continue
        if pasta.exists() and any(pasta.iterdir()):
            parser.error(f"Pasta de saida nao vazia: {pasta}. Use --saida para outra bateria.")
        for nome, caminho in plano["entradas"].items():
            if not Path(caminho).is_file():
                parser.error(f"Arquivo de {nome} nao encontrado: {caminho}")
        pendentes.append(plano)

    falhou = False
    for plano in pendentes:
        codigo = executar_semestre(plano)
        falhou = falhou or codigo != 0
    return int(falhou)


def executar_semestre(plano: dict) -> int:
    pasta = Path(plano["pasta_saida"])
    entradas = plano["entradas"]
    parametros = plano["parametros_gurobi"]
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "configuracao.json").write_text(
        json.dumps(plano, indent=2, ensure_ascii=False), encoding="utf-8")
    resumo = {**plano, "status_execucao_script": "CONCLUIDO"}
    inicio = time.perf_counter()
    print(f"[INICIO] PLI {plano['semestre']}, limite de {parametros['TimeLimit']:g} s: {pasta}")
    try:
        with (pasta / "execucao.out").open("w", encoding="utf-8") as stream:
            with redirect_stdout(stream), redirect_stderr(stream):
                resultado = resolver_pli(
                    arquivo_horarios=str(entradas["horarios"]),
                    arquivo_salas=str(entradas["salas"]),
                    arquivo_salas_preferenciais=str(entradas["preferenciais"]),
                    parametros_gurobi=parametros,
                    gerar_planilhas=False,
                    arquivo_solucao=str(pasta / "melhor.sol"),
                )
                # As chaves de solucao_x sao tuplas; a solucao completa fica no .sol.
                resumo.update({k: v for k, v in resultado.items() if k != "solucao_x"})
    except Exception as exc:
        resumo.update(status_execucao_script="ERRO", erro=str(exc))
        (pasta / "erro.txt").write_text(traceback.format_exc(), encoding="utf-8")
    resumo["tempo_total_s"] = time.perf_counter() - inicio
    escrever_resumos([resumo], pasta)
    print(f"[{resumo['status_execucao_script']}] Resumo salvo em {pasta / 'resumo.csv'}")
    return 1 if resumo["status_execucao_script"] == "ERRO" else 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
