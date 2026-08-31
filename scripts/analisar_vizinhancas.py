import argparse
import contextlib
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extrai_horarios_aula import ExtraiHorariosAula
from extrai_salas import ExtraiSalas
from gera_matriz_distancia import GeraMatrizDistancia


PESO_SALA_NAO_PREFERENCIAL = 150
PESO_NAO_ALOCADA = 2000
PESO_MULTIPLAS_SALAS = 250
PESO_DISPERSAO_FASE = 25


def carregar_dados(arquivo_horarios, arquivo_salas, arquivo_preferenciais):
    salas = ExtraiSalas(arquivo_salas).extrai_salas()
    matriz_dist = GeraMatrizDistancia(salas).gera_matriz()

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        disciplinas, horarios, fases, cursos = ExtraiHorariosAula(
            arquivo_horarios, arquivo_preferenciais
        ).extrai_horarios_aula()

    return salas, matriz_dist, disciplinas, horarios, fases, cursos


def parse_solution_sol(caminho_solucao, disciplinas):
    atribuicoes = {}
    atribuicoes_desconhecidas = []
    padrao = re.compile(r"^x\[(?P<d>[^,]+),(?P<s>[^,]+),(?P<h>[^\]]+)\]\s+(?P<v>[-0-9.]+)")

    with open(caminho_solucao, encoding="utf-8") as arquivo:
        for linha in arquivo:
            resultado = padrao.match(linha.strip())
            if not resultado:
                continue
            valor = round(float(resultado.group("v")))
            if valor != 1:
                continue

            disciplina = resultado.group("d")
            sala = resultado.group("s")
            horario = resultado.group("h")

            if disciplina not in disciplinas:
                atribuicoes_desconhecidas.append(
                    {"disciplina": disciplina, "sala": sala, "horario": horario}
                )
                continue

            atribuicoes[(disciplina, horario)] = sala

    return atribuicoes, atribuicoes_desconhecidas


def variaveis_x(disciplinas, salas, disciplina_ids):
    return sum(
        len(disciplinas[disciplina].horarios_agrupamento()) * len(salas)
        for disciplina in disciplina_ids
    )


def distancia_media_salas(salas_usadas, salas_lista, matriz_dist):
    salas_usadas = sorted(salas_usadas)
    if len(salas_usadas) < 2:
        return 0

    distancias = []
    for indice, sala_i in enumerate(salas_usadas):
        for sala_j in salas_usadas[indice + 1 :]:
            i = salas_lista.index(sala_i)
            j = salas_lista.index(sala_j)
            distancias.append(matriz_dist[i][j])

    return sum(distancias) / len(distancias)


def montar_metricas(salas, matriz_dist, disciplinas, atribuicoes):
    salas_lista = list(salas.keys())
    esperadas = {
        (disciplina, horario)
        for disciplina, dados_disciplina in disciplinas.items()
        for horario in dados_disciplina.horarios_agrupamento()
    }
    nao_alocadas = esperadas - set(atribuicoes)

    salas_por_disciplina = defaultdict(set)
    nao_preferenciais_por_disciplina = Counter()
    nao_preferenciais_por_fase = Counter()
    nao_preferenciais_por_curso = Counter()
    alocacoes_linhas = []

    for disciplina, dados_disciplina in disciplinas.items():
        for horario in dados_disciplina.horarios_agrupamento():
            sala = atribuicoes.get((disciplina, horario))
            nao_alocada = sala is None
            sala_nao_preferencial = False

            if sala is not None:
                salas_por_disciplina[disciplina].add(sala)
                sala_nao_preferencial = (
                    bool(dados_disciplina.salasPreferenciais)
                    and sala not in dados_disciplina.salasPreferenciais
                )

            if sala_nao_preferencial:
                nao_preferenciais_por_disciplina[disciplina] += 1
                nao_preferenciais_por_fase[(dados_disciplina.curso, dados_disciplina.fase)] += 1
                nao_preferenciais_por_curso[dados_disciplina.curso] += 1

            alocacoes_linhas.append(
                {
                    "disciplina": disciplina,
                    "nome_ccr": dados_disciplina.nome_ccr,
                    "curso": dados_disciplina.curso,
                    "fase": dados_disciplina.fase,
                    "horario": horario,
                    "sala": sala or "",
                    "alunos": dados_disciplina.max_alunos_agrupamento(),
                    "salas_preferenciais": ", ".join(dados_disciplina.salasPreferenciais),
                    "nao_alocada": nao_alocada,
                    "sala_nao_preferencial": sala_nao_preferencial,
                }
            )

    salas_por_curso = defaultdict(set)
    salas_por_fase = defaultdict(set)
    disciplinas_por_curso = defaultdict(list)
    disciplinas_por_fase = defaultdict(list)
    nao_alocadas_por_disciplina = Counter()

    for disciplina, dados_disciplina in disciplinas.items():
        disciplinas_por_curso[dados_disciplina.curso].append(disciplina)
        disciplinas_por_fase[(dados_disciplina.curso, dados_disciplina.fase)].append(disciplina)

        for sala in salas_por_disciplina.get(disciplina, set()):
            salas_por_curso[dados_disciplina.curso].add(sala)
            salas_por_fase[(dados_disciplina.curso, dados_disciplina.fase)].add(sala)

        for horario in dados_disciplina.horarios_agrupamento():
            if (disciplina, horario) in nao_alocadas:
                nao_alocadas_por_disciplina[disciplina] += 1

    metricas_disciplinas = []
    for disciplina, dados_disciplina in disciplinas.items():
        salas_usadas = salas_por_disciplina.get(disciplina, set())
        qtd_salas = len(salas_usadas)
        qtd_nao_pref = nao_preferenciais_por_disciplina[disciplina]
        qtd_nao_alocadas = nao_alocadas_por_disciplina[disciplina]
        penalidade_proxy = (
            qtd_nao_pref * PESO_SALA_NAO_PREFERENCIAL
            + qtd_nao_alocadas * PESO_NAO_ALOCADA
            + max(0, qtd_salas - 1) * PESO_MULTIPLAS_SALAS
        )

        metricas_disciplinas.append(
            {
                "disciplina": disciplina,
                "nome_ccr": dados_disciplina.nome_ccr,
                "curso": dados_disciplina.curso,
                "fase": dados_disciplina.fase,
                "alunos": dados_disciplina.max_alunos_agrupamento(),
                "horarios": len(dados_disciplina.horarios_agrupamento()),
                "variaveis_x": len(dados_disciplina.horarios_agrupamento()) * len(salas),
                "salas_usadas_qtd": qtd_salas,
                "salas_usadas": ", ".join(sorted(salas_usadas)),
                "alocacoes_nao_preferenciais": qtd_nao_pref,
                "horarios_nao_alocados": qtd_nao_alocadas,
                "penalidade_proxy": penalidade_proxy,
            }
        )

    metricas_cursos = []
    for curso, disciplina_ids in sorted(disciplinas_por_curso.items()):
        salas_usadas = salas_por_curso[curso]
        fases_do_curso = {
            disciplinas[disciplina].fase for disciplina in disciplina_ids
        }
        metricas_cursos.append(
            {
                "tipo_vizinhanca": "curso",
                "recurso": curso,
                "curso": curso,
                "fase": "",
                "disciplinas": len(disciplina_ids),
                "horarios_disciplina": sum(
                    len(disciplinas[disciplina].horarios_agrupamento())
                    for disciplina in disciplina_ids
                ),
                "variaveis_x": variaveis_x(disciplinas, salas, disciplina_ids),
                "salas_usadas_qtd": len(salas_usadas),
                "salas_usadas": ", ".join(sorted(salas_usadas)),
                "distancia_media_salas": distancia_media_salas(
                    salas_usadas, salas_lista, matriz_dist
                ),
                "alocacoes_nao_preferenciais": nao_preferenciais_por_curso[curso],
                "horarios_nao_alocados": sum(
                    nao_alocadas_por_disciplina[disciplina]
                    for disciplina in disciplina_ids
                ),
                "fases": len(fases_do_curso),
            }
        )

    metricas_fases = []
    for (curso, fase), disciplina_ids in sorted(disciplinas_por_fase.items()):
        salas_usadas = salas_por_fase[(curso, fase)]
        metricas_fases.append(
            {
                "tipo_vizinhanca": "fase",
                "recurso": f"{curso}_{fase}",
                "curso": curso,
                "fase": fase,
                "disciplinas": len(disciplina_ids),
                "horarios_disciplina": sum(
                    len(disciplinas[disciplina].horarios_agrupamento())
                    for disciplina in disciplina_ids
                ),
                "variaveis_x": variaveis_x(disciplinas, salas, disciplina_ids),
                "salas_usadas_qtd": len(salas_usadas),
                "salas_usadas": ", ".join(sorted(salas_usadas)),
                "distancia_media_salas": distancia_media_salas(
                    salas_usadas, salas_lista, matriz_dist
                ),
                "alocacoes_nao_preferenciais": nao_preferenciais_por_fase[(curso, fase)],
                "horarios_nao_alocados": sum(
                    nao_alocadas_por_disciplina[disciplina]
                    for disciplina in disciplina_ids
                ),
            }
        )

    return {
        "esperadas": esperadas,
        "nao_alocadas": nao_alocadas,
        "alocacoes": alocacoes_linhas,
        "disciplinas": metricas_disciplinas,
        "cursos": metricas_cursos,
        "fases": metricas_fases,
        "disciplinas_por_curso": disciplinas_por_curso,
        "disciplinas_por_fase": disciplinas_por_fase,
        "nao_preferenciais_por_disciplina": nao_preferenciais_por_disciplina,
        "nao_alocadas_por_disciplina": nao_alocadas_por_disciplina,
    }


def montar_vizinhancas_candidatas(salas, disciplinas, metricas):
    total_x = variaveis_x(disciplinas, salas, disciplinas.keys())

    linhas = []

    for linha in metricas["fases"]:
        score = (
            linha["alocacoes_nao_preferenciais"] * PESO_SALA_NAO_PREFERENCIAL
            + linha["horarios_nao_alocados"] * PESO_NAO_ALOCADA
            + max(0, linha["salas_usadas_qtd"] - 1) * PESO_DISPERSAO_FASE
        )
        linhas.append(
            {
                **linha,
                "percentual_variaveis": linha["variaveis_x"] / total_x,
                "score_prioridade": score,
                "justificativa": (
                    "Boa candidata quando a fase esta dispersa, fora de salas "
                    "preferenciais ou com horarios nao alocados."
                ),
            }
        )

    for linha in metricas["cursos"]:
        score = (
            linha["alocacoes_nao_preferenciais"] * PESO_SALA_NAO_PREFERENCIAL
            + linha["horarios_nao_alocados"] * PESO_NAO_ALOCADA
            + max(0, linha["salas_usadas_qtd"] - 1) * PESO_DISPERSAO_FASE
        )
        linhas.append(
            {
                **linha,
                "percentual_variaveis": linha["variaveis_x"] / total_x,
                "score_prioridade": score,
                "justificativa": (
                    "Vizinhanca maior; adequada para reorganizar curso inteiro "
                    "quando varias fases parecem afetadas."
                ),
            }
        )

    grupos_demanda = defaultdict(list)
    for disciplina, dados_disciplina in disciplinas.items():
        grupo = round(dados_disciplina.max_alunos_agrupamento() / 10) * 10
        grupos_demanda[grupo].append(disciplina)

    disciplina_por_id = {
        linha["disciplina"]: linha for linha in metricas["disciplinas"]
    }
    for grupo, disciplina_ids in sorted(grupos_demanda.items()):
        if len(disciplina_ids) < 2:
            continue
        qtd_nao_pref = sum(
            disciplina_por_id[disciplina]["alocacoes_nao_preferenciais"]
            for disciplina in disciplina_ids
        )
        qtd_nao_alocadas = sum(
            disciplina_por_id[disciplina]["horarios_nao_alocados"]
            for disciplina in disciplina_ids
        )
        vars_x = variaveis_x(disciplinas, salas, disciplina_ids)
        linhas.append(
            {
                "tipo_vizinhanca": "demanda",
                "recurso": f"demanda_aprox_{grupo}",
                "curso": "",
                "fase": "",
                "disciplinas": len(disciplina_ids),
                "horarios_disciplina": sum(
                    len(disciplinas[disciplina].horarios_agrupamento())
                    for disciplina in disciplina_ids
                ),
                "variaveis_x": vars_x,
                "percentual_variaveis": vars_x / total_x,
                "salas_usadas_qtd": "",
                "salas_usadas": "",
                "distancia_media_salas": "",
                "alocacoes_nao_preferenciais": qtd_nao_pref,
                "horarios_nao_alocados": qtd_nao_alocadas,
                "score_prioridade": (
                    qtd_nao_pref * PESO_SALA_NAO_PREFERENCIAL
                    + qtd_nao_alocadas * PESO_NAO_ALOCADA
                ),
                "justificativa": (
                    "Adaptacao da vizinhanca Courses: disciplinas com demanda "
                    "semelhante tendem a disputar salas compativeis."
                ),
            }
        )

    problematicas = sorted(
        metricas["disciplinas"],
        key=lambda linha: linha["penalidade_proxy"],
        reverse=True,
    )[:20]
    disciplina_ids = [linha["disciplina"] for linha in problematicas if linha["penalidade_proxy"] > 0]
    if disciplina_ids:
        vars_x = variaveis_x(disciplinas, salas, disciplina_ids)
        linhas.append(
            {
                "tipo_vizinhanca": "penalidade_atual",
                "recurso": "top_20_disciplinas_problematicas",
                "curso": "",
                "fase": "",
                "disciplinas": len(disciplina_ids),
                "horarios_disciplina": sum(
                    len(disciplinas[disciplina].horarios_agrupamento())
                    for disciplina in disciplina_ids
                ),
                "variaveis_x": vars_x,
                "percentual_variaveis": vars_x / total_x,
                "salas_usadas_qtd": "",
                "salas_usadas": "",
                "distancia_media_salas": "",
                "alocacoes_nao_preferenciais": sum(
                    linha["alocacoes_nao_preferenciais"] for linha in problematicas
                ),
                "horarios_nao_alocados": sum(
                    linha["horarios_nao_alocados"] for linha in problematicas
                ),
                "score_prioridade": sum(linha["penalidade_proxy"] for linha in problematicas),
                "justificativa": (
                    "Adaptacao da vizinhanca Assignments: libera elementos que "
                    "mais contribuem para a penalidade da solucao atual."
                ),
            }
        )

    return linhas


def escrever_planilha(saida, resumo, metricas, vizinhancas, desconhecidas):
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(saida, engine="openpyxl") as writer:
        pd.DataFrame(resumo).to_excel(writer, sheet_name="Resumo", index=False)
        pd.DataFrame(vizinhancas).sort_values(
            ["score_prioridade", "percentual_variaveis"], ascending=[False, True]
        ).to_excel(writer, sheet_name="Vizinhancas candidatas", index=False)
        pd.DataFrame(metricas["fases"]).sort_values(
            ["alocacoes_nao_preferenciais", "salas_usadas_qtd"],
            ascending=[False, False],
        ).to_excel(writer, sheet_name="Metricas por fase", index=False)
        pd.DataFrame(metricas["cursos"]).sort_values(
            ["alocacoes_nao_preferenciais", "salas_usadas_qtd"],
            ascending=[False, False],
        ).to_excel(writer, sheet_name="Metricas por curso", index=False)
        pd.DataFrame(metricas["disciplinas"]).sort_values(
            "penalidade_proxy", ascending=False
        ).to_excel(writer, sheet_name="Disciplinas problematicas", index=False)
        pd.DataFrame(metricas["alocacoes"]).to_excel(
            writer, sheet_name="Alocacoes detalhadas", index=False
        )
        pd.DataFrame(desconhecidas).to_excel(
            writer, sheet_name="Atribuicoes desconhecidas", index=False
        )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                max_length = 0
                column = column_cells[0].column_letter
                for cell in column_cells[:200]:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, min(len(value), 80))
                worksheet.column_dimensions[column].width = max(12, min(max_length + 2, 55))


def main():
    parser = argparse.ArgumentParser(
        description="Gera planilha diagnostica para vizinhancas LNS sobre uma solucao salva."
    )
    parser.add_argument("--horarios", default="./dados/horarios_2024_1.xlsx")
    parser.add_argument("--salas", default="./dados/salas_2024_1.csv")
    parser.add_argument("--preferenciais", default="./dados/salas_preferenciais_2024.1.xlsx")
    parser.add_argument("--solucao", default="./solution.sol")
    parser.add_argument(
        "--saida", default="./resultados/vizinhancas_metricas_2024_1.xlsx"
    )
    args = parser.parse_args()

    salas, matriz_dist, disciplinas, horarios, fases, cursos = carregar_dados(
        args.horarios, args.salas, args.preferenciais
    )
    atribuicoes, desconhecidas = parse_solution_sol(args.solucao, disciplinas)
    metricas = montar_metricas(salas, matriz_dist, disciplinas, atribuicoes)
    vizinhancas = montar_vizinhancas_candidatas(salas, disciplinas, metricas)

    total_x = variaveis_x(disciplinas, salas, disciplinas.keys())
    resumo = [
        {"metrica": "salas", "valor": len(salas)},
        {"metrica": "disciplinas_ou_agrupamentos", "valor": len(disciplinas)},
        {"metrica": "variaveis_x_total", "valor": total_x},
        {"metrica": "alocacoes_esperadas_disciplina_horario", "valor": len(metricas["esperadas"])},
        {"metrica": "alocacoes_encontradas_na_solucao", "valor": len(atribuicoes)},
        {"metrica": "horarios_nao_alocados", "valor": len(metricas["nao_alocadas"])},
        {"metrica": "atribuicoes_com_disciplina_desconhecida", "valor": len(desconhecidas)},
        {
            "metrica": "alocacoes_em_sala_nao_preferencial",
            "valor": sum(
                linha["alocacoes_nao_preferenciais"]
                for linha in metricas["disciplinas"]
            ),
        },
        {
            "metrica": "disciplinas_com_penalidade_proxy",
            "valor": sum(
                1 for linha in metricas["disciplinas"] if linha["penalidade_proxy"] > 0
            ),
        },
    ]

    escrever_planilha(args.saida, resumo, metricas, vizinhancas, desconhecidas)
    print(f"Planilha gerada em {args.saida}")


if __name__ == "__main__":
    main()
