from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alocador_salas.optimization.main_fix_and_optimize import executar_fix_and_optimize


@dataclass(frozen=True)
class ExperimentoFixOpt:
    nome: str
    tipo_vizinhanca: str
    ordem_cursos: str = "alfabetica"
    usar_seed: bool = False


EXPERIMENTOS_PADRAO = (
    ExperimentoFixOpt(
        nome="turno_curso_depois_cursos_pares",
        tipo_vizinhanca="turno_curso_depois_cursos_pares",
    ),
    ExperimentoFixOpt(
        nome="prog_ate_2_depois_turno_curso",
        tipo_vizinhanca="cursos_progr_ate_2_dia_turno_curso",
    ),
    ExperimentoFixOpt(
        nome="aleatorio_cursos_pares_turno_cursos_nao_agrupado",
        tipo_vizinhanca="hibrida_dia_turno_curso_pares",
        ordem_cursos="aleatoria",
        usar_seed=True,
    ),
    ExperimentoFixOpt(
        nome="aleatorio_cursos_pares_turno_curso_agrupado",
        tipo_vizinhanca="hibrida_pares_dia_turno_curso",
        ordem_cursos="aleatoria",
        usar_seed=True,
    ),
    ExperimentoFixOpt(
        nome="turno_cursos_pares",
        tipo_vizinhanca="turno_cursos_pares",
    ),
)


def semestre_para_preferenciais(semestre: str) -> str:
    return semestre.replace("_", ".")


def caminhos_entrada(
    semestre: str,
    raiz_dados: str | Path = "dados",
    horarios: str | Path | None = None,
    salas: str | Path | None = None,
    preferenciais: str | Path | None = None,
) -> dict[str, Path]:
    pasta_semestre = Path(raiz_dados) / semestre
    return {
        "horarios": Path(horarios) if horarios else pasta_semestre / f"horarios_{semestre}.xlsx",
        "salas": Path(salas) if salas else pasta_semestre / f"salas_{semestre}.csv",
        "preferenciais": (
            Path(preferenciais)
            if preferenciais
            else pasta_semestre / f"salas_preferenciais_{semestre_para_preferenciais(semestre)}.xlsx"
        ),
    }


def selecionar_experimentos(nomes: Iterable[str]) -> list[ExperimentoFixOpt]:
    nomes = list(nomes)
    if not nomes:
        return list(EXPERIMENTOS_PADRAO)

    por_nome = {experimento.nome: experimento for experimento in EXPERIMENTOS_PADRAO}
    faltantes = [nome for nome in nomes if nome not in por_nome]
    if faltantes:
        disponiveis = ", ".join(sorted(por_nome))
        raise ValueError(
            f"Experimentos desconhecidos: {', '.join(faltantes)}. "
            f"Disponiveis: {disponiveis}"
        )
    return [por_nome[nome] for nome in nomes]


def pasta_saida_experimento(raiz_saida: str | Path, semestre: str, nome: str) -> Path:
    return Path(raiz_saida) / semestre / "fixopt_vizinhancas" / nome


def resumo_resultado(
    experimento: ExperimentoFixOpt,
    pasta_saida: Path,
    resultado: dict | None = None,
    erro: str | None = None,
) -> dict:
    resultado = resultado or {}
    return {
        "experimento": experimento.nome,
        "tipo_vizinhanca": experimento.tipo_vizinhanca,
        "ordem_cursos": experimento.ordem_cursos,
        "status_execucao_script": "ERRO" if erro else "CONCLUIDO",
        "erro": erro,
        "status": resultado.get("status"),
        "objetivo_inicial": resultado.get("objetivo_inicial"),
        "objetivo_final": resultado.get("objetivo_final"),
        "ganho_absoluto": resultado.get("ganho_absoluto"),
        "passadas_executadas": resultado.get("passadas_executadas"),
        "total_iteracoes": resultado.get("total_iteracoes"),
        "melhorias_aceitas": resultado.get("melhorias_aceitas"),
        "tempo_total_s": resultado.get("tempo_total_s"),
        "arquivo_melhor_solucao": str(pasta_saida / "melhor.sol"),
        "arquivo_log_csv": str(pasta_saida / "historico.csv"),
        "arquivo_log_json": str(pasta_saida / "historico.json"),
        "arquivo_stdout": str(pasta_saida / "execucao.out"),
    }


def escrever_resumos(resumos: list[dict], pasta_raiz: Path) -> None:
    pasta_raiz.mkdir(parents=True, exist_ok=True)
    (pasta_raiz / "resumo.json").write_text(
        json.dumps(resumos, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    campos: list[str] = []
    for resumo in resumos:
        for campo in resumo:
            if campo not in campos:
                campos.append(campo)
    with (pasta_raiz / "resumo.csv").open("w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resumos)


def executar_experimento(
    experimento: ExperimentoFixOpt,
    entradas: dict[str, Path],
    pasta_saida: Path,
    tempo_modelo: float,
    tempo_heuristica: float,
    tempo_subproblema: float,
    tempo_total: float | None,
    apenas_uma_passada: bool,
    salvar_candidatos: bool,
    seed: int | None,
) -> dict:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    arquivo_saida = pasta_saida / "execucao.out"
    seed_efetiva = seed if experimento.usar_seed else None

    with arquivo_saida.open("w", encoding="utf-8") as stream:
        with redirect_stdout(stream), redirect_stderr(stream):
            print(f"Experimento: {experimento.nome}")
            print(f"Tipo de vizinhanca: {experimento.tipo_vizinhanca}")
            print(f"Ordem de cursos: {experimento.ordem_cursos}")
            print(f"Seed: {seed_efetiva}")
            return executar_fix_and_optimize(
                arquivo_horarios=str(entradas["horarios"]),
                arquivo_salas=str(entradas["salas"]),
                arquivo_salas_preferenciais=str(entradas["preferenciais"]),
                arquivo_melhor_solucao=str(pasta_saida / "melhor.sol"),
                arquivo_log_csv=str(pasta_saida / "historico.csv"),
                arquivo_log_json=str(pasta_saida / "historico.json"),
                tempo_modelo_inicial=tempo_modelo,
                tempo_heuristica_inicial=tempo_heuristica,
                tempo_subproblema=tempo_subproblema,
                tempo_total_maximo=tempo_total,
                apenas_uma_passada=apenas_uma_passada,
                salvar_candidatos=salvar_candidatos,
                tipo_vizinhanca=experimento.tipo_vizinhanca,
                ordem_cursos=experimento.ordem_cursos,
                seed_ordem_cursos=seed_efetiva,
            )


def main_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Roda as vizinhancas Fix-and-Optimize de um semestre."
    )
    parser.add_argument("--semestre", required=True, help="Ex.: 2024_1")
    parser.add_argument("--raiz-dados", default="dados")
    parser.add_argument("--saida", default="resultados/experimentos")
    parser.add_argument("--horarios", default="")
    parser.add_argument("--salas", default="")
    parser.add_argument("--preferenciais", default="")
    parser.add_argument("--tempo-modelo", type=float, default=180)
    parser.add_argument("--tempo-heuristica", type=float, default=180)
    parser.add_argument("--tempo-subproblema", type=float, default=600)
    parser.add_argument("--tempo-total", type=float, default=14400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--somente", action="append", default=[],
                        help="Nome do experimento a executar. Pode repetir.")
    parser.add_argument("--pular-existentes", action="store_true")
    parser.add_argument("--apenas-uma-passada", action="store_true")
    parser.add_argument("--salvar-candidatos", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entradas = caminhos_entrada(
        semestre=args.semestre,
        raiz_dados=args.raiz_dados,
        horarios=args.horarios or None,
        salas=args.salas or None,
        preferenciais=args.preferenciais or None,
    )
    experimentos = selecionar_experimentos(args.somente)
    pasta_raiz = Path(args.saida) / args.semestre / "fixopt_vizinhancas"

    plano = []
    for experimento in experimentos:
        pasta_saida = pasta_saida_experimento(args.saida, args.semestre, experimento.nome)
        plano.append({
            **asdict(experimento),
            "seed": args.seed if experimento.usar_seed else None,
            "pasta_saida": str(pasta_saida),
        })

    if args.dry_run:
        print(json.dumps({
            "semestre": args.semestre,
            "entradas": {nome: str(caminho) for nome, caminho in entradas.items()},
            "pasta_raiz": str(pasta_raiz),
            "experimentos": plano,
        }, indent=2, ensure_ascii=False))
        return 0

    resumos: list[dict] = []
    for experimento in experimentos:
        pasta_saida = pasta_saida_experimento(args.saida, args.semestre, experimento.nome)
        if args.pular_existentes and (pasta_saida / "historico.json").exists():
            resumo = resumo_resultado(experimento, pasta_saida)
            resumo["status_execucao_script"] = "PULADO"
            resumos.append(resumo)
            print(f"[PULADO] {experimento.nome}")
            continue

        print(f"[INICIO] {experimento.nome}")
        try:
            resultado = executar_experimento(
                experimento=experimento,
                entradas=entradas,
                pasta_saida=pasta_saida,
                tempo_modelo=args.tempo_modelo,
                tempo_heuristica=args.tempo_heuristica,
                tempo_subproblema=args.tempo_subproblema,
                tempo_total=args.tempo_total,
                apenas_uma_passada=args.apenas_uma_passada,
                salvar_candidatos=args.salvar_candidatos,
                seed=args.seed,
            )
            resumos.append(resumo_resultado(experimento, pasta_saida, resultado=resultado))
            print(f"[OK] {experimento.nome}")
        except Exception as exc:  # pragma: no cover - caminho operacional
            pasta_saida.mkdir(parents=True, exist_ok=True)
            erro = "".join(traceback.format_exception(exc))
            (pasta_saida / "erro.txt").write_text(erro, encoding="utf-8")
            resumos.append(resumo_resultado(experimento, pasta_saida, erro=str(exc)))
            print(f"[ERRO] {experimento.nome}: {exc}")

    escrever_resumos(resumos, pasta_raiz)
    print(f"Resumo salvo em {pasta_raiz / 'resumo.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
