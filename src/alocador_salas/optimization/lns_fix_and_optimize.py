"""Utilitarios para LNS com fix-and-optimize no PAS.

As funcoes deste modulo evitam depender diretamente do Gurobi sempre que
possivel. Isso facilita testar a logica de vizinhancas e deixa o `solve.py`
responsavel apenas por construir e resolver o modelo.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from alocador_salas.domain.horario import (
    DIAS_VALIDOS,
    TURNOS_VALIDOS,
    Turno,
    turno_da_faixa,
)


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
    metadados: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PenalidadeDisciplina:
    disciplina: str
    horarios_nao_alocados: int
    alocacoes_nao_preferenciais: int
    salas_usadas: frozenset[str]
    score: float


@dataclass(frozen=True)
class IndicesAlocacao:
    sala_por_disciplina_horario: dict[tuple[str, str], str]
    ocupante_por_sala_horario: dict[tuple[str, str], str]
    salas_por_disciplina: dict[str, frozenset[str]]


PESO_MULTIPLAS_SALAS = 250
PESO_SALA_NAO_PREFERENCIAL = 150
PESO_NAO_ALOCADA = 2000
PESO_DISPERSAO_FASE = 5
PESO_DISPERSAO_CURSO = 0.5


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


def disciplinas_do_dia_turno(
    disciplinas,
    dia: int,
    turno: Turno,
) -> set[str]:
    """Seleciona disciplinas com ao menos uma aula no dia e turno informados."""
    if dia not in DIAS_VALIDOS:
        raise ValueError(f"Dia de horario invalido: {dia}. Esperado valor entre 2 e 7.")
    if turno not in TURNOS_VALIDOS:
        raise ValueError(
            f"Turno invalido: {turno}. Esperado um dos valores {TURNOS_VALIDOS}."
        )

    selecionadas: set[str] = set()
    for codigo, disciplina in disciplinas.items():
        horarios = disciplina.horarios_agrupamento()
        if any(
            horario.dia == dia and turno_da_faixa(horario.faixa) == turno
            for horario in horarios.values()
        ):
            selecionadas.add(codigo)

    return selecionadas


def vizinhanca_por_dia_turno(
    disciplinas,
    dia: int,
    turno: Turno,
) -> Vizinhanca:
    liberadas = disciplinas_do_dia_turno(disciplinas, dia, turno)
    return Vizinhanca(
        tipo="dia_turno",
        recurso=f"{dia}_{turno}",
        disciplinas_liberadas=frozenset(liberadas),
        justificativa=(
            "Libera disciplinas inteiras que possuem ao menos uma aula "
            "no dia e turno selecionados."
        ),
    )


def vizinhancas_por_dia_turno(disciplinas) -> list[Vizinhanca]:
    """Gera as vizinhancas nao vazias de dia/turno em ordem deterministica."""
    vizinhancas: list[Vizinhanca] = []
    for dia in sorted(DIAS_VALIDOS):
        for turno in TURNOS_VALIDOS:
            vizinhanca = vizinhanca_por_dia_turno(disciplinas, dia, turno)
            if vizinhanca.disciplinas_liberadas:
                vizinhancas.append(vizinhanca)

    return vizinhancas


def indexar_alocacoes(solucao_x: SolucaoX) -> IndicesAlocacao:
    """Cria indices compactos apenas com as atribuicoes ativas da incumbente."""
    por_disciplina_horario: dict[tuple[str, str], str] = {}
    por_sala_horario: dict[tuple[str, str], str] = {}
    salas_por_disciplina: dict[str, set[str]] = defaultdict(set)
    for (disciplina, sala, horario), valor in solucao_x.items():
        if valor <= 0:
            continue
        por_disciplina_horario[(disciplina, horario)] = sala
        por_sala_horario[(sala, horario)] = disciplina
        salas_por_disciplina[disciplina].add(sala)
    return IndicesAlocacao(
        sala_por_disciplina_horario=por_disciplina_horario,
        ocupante_por_sala_horario=por_sala_horario,
        salas_por_disciplina={
            disciplina: frozenset(salas)
            for disciplina, salas in salas_por_disciplina.items()
        },
    )


def _distancia_total(salas: set[str], salas_lista: list[str], matriz_dist: list) -> float:
    indices = {sala: indice for indice, sala in enumerate(salas_lista)}
    conhecidas = sorted((sala for sala in salas if sala in indices), key=indices.get)
    return sum(
        matriz_dist[indices[sala_i]][indices[sala_j]]
        for posicao, sala_i in enumerate(conhecidas)
        for sala_j in conhecidas[posicao + 1 :]
    )


def calcular_penalidades_disciplinas(instancia, solucao_x: SolucaoX) -> list[PenalidadeDisciplina]:
    """Pontua disciplinas pela penalidade local e pela dispersao dos seus grupos."""
    indices = indexar_alocacoes(solucao_x)
    salas_fase: dict[tuple[str, int], set[str]] = defaultdict(set)
    salas_curso: dict[str, set[str]] = defaultdict(set)
    for codigo, disciplina in instancia.disciplinas.items():
        salas = set(indices.salas_por_disciplina.get(codigo, ()))
        salas_fase[(disciplina.curso, disciplina.fase)].update(salas)
        salas_curso[disciplina.curso].update(salas)

    resultado = []
    for codigo, disciplina in instancia.disciplinas.items():
        horarios = disciplina.horarios_agrupamento()
        atribuicoes = [
            indices.sala_por_disciplina_horario.get((codigo, horario))
            for horario in horarios
        ]
        nao_alocados = sum(sala is None for sala in atribuicoes)
        preferenciais = set(disciplina.salasPreferenciais or ())
        nao_preferenciais = sum(
            sala is not None and sala not in preferenciais for sala in atribuicoes
        )
        salas_usadas = set(indices.salas_por_disciplina.get(codigo, ()))
        dispersao_fase = _distancia_total(
            salas_fase[(disciplina.curso, disciplina.fase)],
            instancia.salas_lista,
            instancia.matriz_dist,
        )
        dispersao_curso = _distancia_total(
            salas_curso[disciplina.curso],
            instancia.salas_lista,
            instancia.matriz_dist,
        )
        score = (
            nao_alocados * PESO_NAO_ALOCADA
            + nao_preferenciais * PESO_SALA_NAO_PREFERENCIAL
            + max(0, len(salas_usadas) - 1) * PESO_MULTIPLAS_SALAS
            + dispersao_fase * PESO_DISPERSAO_FASE
            + dispersao_curso * PESO_DISPERSAO_CURSO
        )
        resultado.append(
            PenalidadeDisciplina(
                disciplina=codigo,
                horarios_nao_alocados=nao_alocados,
                alocacoes_nao_preferenciais=nao_preferenciais,
                salas_usadas=frozenset(salas_usadas),
                score=score,
            )
        )
    return sorted(resultado, key=lambda item: (-item.score, item.disciplina))


def _distancia_media_para_salas(
    sala: str,
    referencias: set[str],
    salas_lista: list[str],
    matriz_dist: list,
) -> float:
    if not referencias:
        return 0.0
    indices = {nome: indice for indice, nome in enumerate(salas_lista)}
    if sala not in indices:
        return float("inf")
    distancias = [
        matriz_dist[indices[sala]][indices[referencia]]
        for referencia in referencias
        if referencia in indices and referencia != sala
    ]
    return sum(distancias) / len(distancias) if distancias else 0.0


def salas_candidatas_para_disciplina(
    instancia,
    solucao_x: SolucaoX,
    codigo_disciplina: str,
    max_salas: int = 5,
) -> list[str]:
    """Seleciona salas compativeis priorizando preferencia e proximidade do grupo."""
    if max_salas <= 0:
        raise ValueError("max_salas deve ser maior que zero.")
    disciplina = instancia.disciplinas[codigo_disciplina]
    indices = indexar_alocacoes(solucao_x)
    preferenciais = set(disciplina.salasPreferenciais or ())
    salas_disciplina = set(indices.salas_por_disciplina.get(codigo_disciplina, ()))
    salas_grupo: set[str] = set()
    for outro_codigo, outra in instancia.disciplinas.items():
        if (
            outra.curso == disciplina.curso
            and outra.fase == disciplina.fase
        ):
            salas_grupo.update(indices.salas_por_disciplina.get(outro_codigo, ()))

    compativeis = [
        sala
        for sala in instancia.salas_lista
        if instancia.salas[sala].capacidade >= disciplina.max_alunos_agrupamento()
    ]
    compativeis.sort(
        key=lambda sala: (
            sala not in preferenciais,
            sala not in salas_disciplina,
            sala not in salas_grupo,
            _distancia_media_para_salas(
                sala, salas_grupo, instancia.salas_lista, instancia.matriz_dist
            ),
            sala,
        )
    )
    return compativeis[:max_salas]


def bloqueadores_das_disciplinas(
    instancia,
    solucao_x: SolucaoX,
    sementes: Iterable[str],
    max_salas_candidatas: int = 5,
) -> tuple[set[str], Counter]:
    """Encontra disciplinas que ocupam salas candidatas nos mesmos horarios."""
    sementes = set(sementes)
    indices = indexar_alocacoes(solucao_x)
    relevancia: Counter = Counter()
    for codigo in sorted(sementes):
        salas = salas_candidatas_para_disciplina(
            instancia, solucao_x, codigo, max_salas_candidatas
        )
        for horario in instancia.disciplinas[codigo].horarios_agrupamento():
            for sala in salas:
                bloqueador = indices.ocupante_por_sala_horario.get((sala, horario))
                if bloqueador is not None and bloqueador not in sementes:
                    relevancia[bloqueador] += 1
    return set(relevancia), relevancia


def quantidade_variaveis_x(instancia, disciplinas: Iterable[str]) -> int:
    return sum(
        len(instancia.disciplinas[codigo].horarios_agrupamento())
        * len(instancia.salas)
        for codigo in set(disciplinas)
    )


def vizinhanca_penalidade_bloqueadores(
    instancia,
    solucao_x: SolucaoX,
    sementes_por_vizinhanca: int = 5,
    max_salas_candidatas: int = 5,
    percentual_x_maximo: float = 0.12,
    sementes_ignoradas: Iterable[str] = (),
) -> Vizinhanca | None:
    """Monta uma vizinhanca limitada com sementes penalizadas e bloqueadores."""
    if sementes_por_vizinhanca <= 0:
        raise ValueError("sementes_por_vizinhanca deve ser maior que zero.")
    if not 0 < percentual_x_maximo <= 1:
        raise ValueError("percentual_x_maximo deve estar no intervalo (0, 1].")

    ranking = [
        item
        for item in calcular_penalidades_disciplinas(instancia, solucao_x)
        if item.score > 0 and item.disciplina not in set(sementes_ignoradas)
    ]
    if not ranking:
        return None

    total_x = quantidade_variaveis_x(instancia, instancia.disciplinas)
    limite_x = max(1, int(total_x * percentual_x_maximo))
    sementes: list[str] = []
    for item in ranking:
        candidato = sementes + [item.disciplina]
        if sementes and quantidade_variaveis_x(instancia, candidato) > limite_x:
            continue
        sementes.append(item.disciplina)
        if len(sementes) >= sementes_por_vizinhanca:
            break
    if not sementes:
        sementes = [ranking[0].disciplina]

    bloqueadores, relevancia = bloqueadores_das_disciplinas(
        instancia,
        solucao_x,
        sementes,
        max_salas_candidatas=max_salas_candidatas,
    )
    scores = {item.disciplina: item.score for item in ranking}
    liberadas = set(sementes)
    for bloqueador in sorted(
        bloqueadores,
        key=lambda codigo: (-relevancia[codigo], -scores.get(codigo, 0), codigo),
    ):
        candidato = liberadas | {bloqueador}
        if quantidade_variaveis_x(instancia, candidato) <= limite_x:
            liberadas.add(bloqueador)

    variaveis_livres = quantidade_variaveis_x(instancia, liberadas)
    recurso = "seeds_" + "-".join(sementes)
    bloqueadores_incluidos = sorted(liberadas - set(sementes))
    return Vizinhanca(
        tipo="penalidade_bloqueadores",
        recurso=recurso,
        disciplinas_liberadas=frozenset(liberadas),
        justificativa=(
            "Libera disciplinas penalizadas e ocupantes de suas salas "
            "candidatas nos mesmos horarios."
        ),
        metadados={
            "sementes": ";".join(sementes),
            "bloqueadores": ";".join(bloqueadores_incluidos),
            "quantidade_sementes": len(sementes),
            "quantidade_bloqueadores": len(bloqueadores_incluidos),
            "score_sementes": round(sum(scores[codigo] for codigo in sementes), 2),
            "conflitos_encontrados": sum(relevancia.values()),
            "variaveis_x_estimadas": variaveis_livres,
            "percentual_x_estimado": round(variaveis_livres / total_x, 6),
            "limite_variaveis_x": limite_x,
            "profundidade_expansao": 1,
        },
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
