import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.run_fixopt_semestre import (
    EXPERIMENTOS_PADRAO,
    caminhos_entrada,
    pasta_saida_experimento,
    selecionar_experimentos,
    semestre_para_preferenciais,
)


class TestRunFixoptSemestre(unittest.TestCase):
    def test_semestre_para_preferenciais_troca_underscore_por_ponto(self):
        self.assertEqual(semestre_para_preferenciais("2024_1"), "2024.1")

    def test_caminhos_entrada_por_convencao_do_semestre(self):
        caminhos = caminhos_entrada("2024_1")

        self.assertEqual(caminhos["horarios"], Path("dados/2024_1/horarios_2024_1.xlsx"))
        self.assertEqual(caminhos["salas"], Path("dados/2024_1/salas_2024_1.csv"))
        self.assertEqual(
            caminhos["preferenciais"],
            Path("dados/2024_1/salas_preferenciais_2024.1.xlsx"),
        )

    def test_experimentos_padrao_mapeiam_nomes_para_tipos_existentes(self):
        mapeamento = {
            experimento.nome: (
                experimento.tipo_vizinhanca,
                experimento.ordem_cursos,
                experimento.usar_seed,
            )
            for experimento in EXPERIMENTOS_PADRAO
        }

        self.assertEqual(
            mapeamento["turno_curso_depois_cursos_pares"],
            ("turno_curso_depois_cursos_pares", "alfabetica", False),
        )
        self.assertEqual(
            mapeamento["prog_ate_2_depois_turno_curso"],
            ("cursos_progr_ate_2_dia_turno_curso", "alfabetica", False),
        )
        self.assertEqual(
            mapeamento["aleatorio_cursos_pares_turno_cursos_nao_agrupado"],
            ("hibrida_dia_turno_curso_pares", "aleatoria", True),
        )
        self.assertEqual(
            mapeamento["aleatorio_cursos_pares_turno_curso_agrupado"],
            ("hibrida_pares_dia_turno_curso", "aleatoria", True),
        )
        self.assertEqual(
            mapeamento["turno_cursos_pares"],
            ("turno_cursos_pares", "alfabetica", False),
        )

    def test_selecionar_experimentos_respeita_ordem_solicitada(self):
        selecionados = selecionar_experimentos([
            "turno_cursos_pares",
            "prog_ate_2_depois_turno_curso",
        ])

        self.assertEqual(
            [experimento.nome for experimento in selecionados],
            ["turno_cursos_pares", "prog_ate_2_depois_turno_curso"],
        )

    def test_selecionar_experimentos_rejeita_nome_desconhecido(self):
        with self.assertRaisesRegex(ValueError, "Experimentos desconhecidos"):
            selecionar_experimentos(["nao_existe"])

    def test_pasta_saida_experimento_usa_semestre_e_nome(self):
        self.assertEqual(
            pasta_saida_experimento("resultados/experimentos", "2024_1", "modo"),
            Path("resultados/experimentos/2024_1/fixopt_vizinhancas/modo"),
        )

    def test_dry_run_imprime_plano_sem_executar_gurobi(self):
        script = Path("scripts/run_fixopt_semestre.py")
        processo = subprocess.run(
            [
                sys.executable,
                str(script),
                "--semestre",
                "2024_1",
                "--somente",
                "turno_cursos_pares",
                "--dry-run",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        plano = json.loads(processo.stdout)
        self.assertEqual(plano["semestre"], "2024_1")
        self.assertEqual(len(plano["experimentos"]), 1)
        self.assertEqual(plano["experimentos"][0]["nome"], "turno_cursos_pares")
        self.assertEqual(
            plano["experimentos"][0]["pasta_saida"],
            "resultados/experimentos/2024_1/fixopt_vizinhancas/turno_cursos_pares",
        )


if __name__ == "__main__":
    unittest.main()
