import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alocador_salas.optimization.solve import main


def resumo_serializavel(resultado):
    campos = [
        "cenario",
        "status_nome",
        "solucoes",
        "objetivo",
        "bound",
        "gap",
        "tempo",
        "restricoes_removidas",
        "parametros_gurobi",
    ]
    return {campo: resultado.get(campo) for campo in campos}


def cenarios(time_limit, no_rel_heur_time):
    parametros_base = {"TimeLimit": time_limit}
    parametros_viabilidade = {
        "TimeLimit": time_limit,
        "MIPFocus": 1,
        "NoRelHeurTime": no_rel_heur_time,
    }

    return [
        ("base_tlim", [], parametros_base),
        ("viabilidade_mipfocus_norel", [], parametros_viabilidade),
        ("viabilidade_heuristics_020", [], {**parametros_viabilidade, "Heuristics": 0.20}),
        ("viabilidade_norel_work", [], {"TimeLimit": time_limit, "MIPFocus": 1, "NoRelHeurWork": no_rel_heur_time}),
        ("primeira_solucao", [], {"TimeLimit": time_limit, "MIPFocus": 1, "SolutionLimit": 1}),
        ("melhoria_apos_60s", [], {"TimeLimit": time_limit, "MIPFocus": 1, "ImproveStartTime": 60}),
        ("sem_c5_c6", ["c5", "c6"], parametros_viabilidade),
        ("sem_c7_c8", ["c7", "c8"], parametros_viabilidade),
        ("sem_c5_c6_c7_c8", ["c5", "c6", "c7", "c8"], parametros_viabilidade),
        ("sem_c3", ["c3"], parametros_viabilidade),
        ("sem_c1_c2", ["c1", "c2"], parametros_viabilidade),
        ("sem_c5_c6_tlim", ["c5", "c6"], parametros_base),
        ("sem_c7_c8_tlim", ["c7", "c8"], parametros_base),
        ("sem_c5_c6_c7_c8_tlim", ["c5", "c6", "c7", "c8"], parametros_base),
        ("sem_c3_tlim", ["c3"], parametros_base),
        ("sem_c1_c2_tlim", ["c1", "c2"], parametros_base),
    ]


def main_cli():
    parser = argparse.ArgumentParser(description="Roda experimentos Gurobi para comparar solucoes iniciais.")
    parser.add_argument("--horarios", default="./dados/2024_1/horarios_2024_1.xlsx")
    parser.add_argument("--salas", default="./dados/2024_1/salas_2024_1.csv")
    parser.add_argument("--preferenciais", default="./dados/2024_1/salas_preferenciais_2024.1.xlsx")
    parser.add_argument("--time-limit", type=float, default=300)
    parser.add_argument("--no-rel-heur-time", type=float, default=300)
    parser.add_argument("--saida", default="")
    parser.add_argument("--cenario", action="append", default=[], help="Nome de cenario a executar. Pode repetir.")
    parser.add_argument("--append", action="store_true", help="Adiciona resultados ao CSV existente em vez de sobrescrever.")
    args = parser.parse_args()

    saida = Path(args.saida or f"resultados/experimentos/resultados_gurobi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    saida.parent.mkdir(parents=True, exist_ok=True)
    resultados = []
    todos_cenarios = cenarios(args.time_limit, args.no_rel_heur_time)
    if args.cenario:
        nomes = set(args.cenario)
        todos_cenarios = [cenario for cenario in todos_cenarios if cenario[0] in nomes]
        encontrados = {cenario[0] for cenario in todos_cenarios}
        faltantes = nomes - encontrados
        if faltantes:
            raise ValueError(f"Cenarios nao encontrados: {', '.join(sorted(faltantes))}")

    for nome, restricoes_removidas, parametros in todos_cenarios:
        print(f"\n=== {nome} ===")
        resultado = main(
            args.horarios,
            args.salas,
            args.preferenciais,
            restricoes_removidas=restricoes_removidas,
            parametros_gurobi=parametros,
            gerar_planilhas=False,
        )
        resultado["cenario"] = nome
        resultados.append(resultado)
        print("RESULTADO_JSON=" + json.dumps(resumo_serializavel(resultado), ensure_ascii=False, sort_keys=True))

    campos = [
        "cenario",
        "status_nome",
        "solucoes",
        "objetivo",
        "bound",
        "gap",
        "tempo",
        "restricoes_removidas",
        "parametros_gurobi",
    ]
    modo = "a" if args.append else "w"
    escrever_cabecalho = not args.append or not saida.exists() or saida.stat().st_size == 0
    with saida.open(modo, newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        if escrever_cabecalho:
            writer.writeheader()
        for resultado in resultados:
            linha = resultado.copy()
            linha["restricoes_removidas"] = ",".join(linha["restricoes_removidas"])
            linha["parametros_gurobi"] = json.dumps(linha["parametros_gurobi"], sort_keys=True)
            writer.writerow({campo: linha.get(campo) for campo in campos})

    print(f"\nResultados salvos em {saida}")


if __name__ == "__main__":
    main_cli()
