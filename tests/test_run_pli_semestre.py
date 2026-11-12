import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from scripts.run_pli_semestre import main_cli


class TestRunPliSemestre(unittest.TestCase):
    def test_varios_semestres_limite_individual_e_continua_apos_falha(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli",
            side_effect=[RuntimeError("falha no primeiro"), {"status_nome": "TIME_LIMIT"}],
        ) as solver, redirect_stdout(io.StringIO()):
            self.assertEqual(main_cli(["--semestre", "2024_1", "2024_2",
                                       "--saida", tmp]), 1)
            self.assertEqual(solver.call_count, 2)
            for semestre, chamada in zip(("2024_1", "2024_2"), solver.call_args_list):
                self.assertEqual(chamada.kwargs["parametros_gurobi"]["TimeLimit"], 14400)
                self.assertIn(semestre, chamada.kwargs["arquivo_horarios"])
                pasta = Path(tmp) / semestre / "pli" / "modelo_completo"
                self.assertTrue((pasta / "resumo.json").is_file())

    def test_dry_run_lista_repeticao_e_duplicatas(self):
        with redirect_stdout(io.StringIO()) as stream:
            main_cli(["--semestre", "2024_1", "2024_2", "--semestre", "2024_1",
                      "2025_1", "--dry-run"])
        planos = json.loads(stream.getvalue())["experimentos"]
        self.assertEqual([p["semestre"] for p in planos], ["2024_1", "2024_2", "2025_1"])
        self.assertTrue(all(p["parametros_gurobi"]["TimeLimit"] == 14400 for p in planos))

    def test_valida_toda_bateria_antes_de_executar(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli"
        ) as solver, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main_cli(["--semestre", "2024_1", "inexistente", "--saida", tmp])
            with self.assertRaises(SystemExit):
                main_cli(["--semestre", "2024_1", "2024_2", "--horarios", "mesmo.xlsx"])
            solver.assert_not_called()

    def test_dry_run_quatro_horas_sem_solver_nem_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli"
        ) as solver, redirect_stdout(io.StringIO()) as stream:
            saida = Path(tmp) / "saida"
            self.assertEqual(main_cli(["--semestre", "2026_2", "--saida", str(saida),
                                       "--dry-run"]), 0)
            plano = json.loads(stream.getvalue())
            self.assertEqual(plano["parametros_gurobi"]["TimeLimit"], 14400)
            self.assertEqual(plano["parametros_gurobi"]["NoRelHeurTime"], 0)
            self.assertTrue(plano["entradas"]["preferenciais"].endswith("2026.2.xlsx"))
            self.assertFalse(saida.exists())
            solver.assert_not_called()

    def test_execucao_salva_metricas_sem_serializar_tuplas_e_pula_existentes(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli",
            return_value={"status_nome": "TIME_LIMIT", "objetivo": 123,
                          "bound": 100, "gap": 0.187, "solucoes": 1,
                          "solucao_x": {("d", "s", "h"): 1}},
        ) as solver, redirect_stdout(io.StringIO()):
            args = ["--semestre", "2024_1", "--saida", tmp,
                    "--tempo-total", "25200", "--mipfocus", "1",
                    "--tempo-heuristica", "300"]
            self.assertEqual(main_cli(args), 0)
            kwargs = solver.call_args.kwargs
            self.assertFalse(kwargs["gerar_planilhas"])
            self.assertEqual(kwargs["parametros_gurobi"]["TimeLimit"], 25200)
            self.assertEqual(kwargs["parametros_gurobi"]["NoRelHeurTime"], 300)
            pasta = Path(tmp) / "2024_1" / "pli" / "modelo_completo"
            resumo = json.loads((pasta / "resumo.json").read_text())[0]
            self.assertEqual(resumo["objetivo"], 123)
            self.assertEqual(resumo["status_nome"], "TIME_LIMIT")
            self.assertNotIn("solucao_x", resumo)
            self.assertTrue((pasta / "resumo.csv").is_file())
            self.assertEqual(main_cli(args + ["--pular-existentes"]), 0)
            self.assertEqual(solver.call_count, 1)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main_cli(args)
            self.assertEqual(solver.call_count, 1)

    def test_erro_do_solver_retorna_falha_e_registra_diagnostico(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli", side_effect=RuntimeError("falha")
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(main_cli(["--semestre", "2024_1", "--saida", tmp]), 1)
            pasta = Path(tmp) / "2024_1" / "pli" / "modelo_completo"
            resumo = json.loads((pasta / "resumo.json").read_text())[0]
            self.assertEqual(resumo["status_execucao_script"], "ERRO")
            self.assertIn("falha", (pasta / "erro.txt").read_text())

    def test_rejeita_tempo_invalido_e_entrada_ausente(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
            "scripts.run_pli_semestre.resolver_pli"
        ) as solver, redirect_stderr(io.StringIO()):
            for tempo in ("0", "-1", "nan", "inf"):
                with self.assertRaises(SystemExit):
                    main_cli(["--semestre", "2024_1", "--tempo-total", tempo])
            with self.assertRaises(SystemExit):
                main_cli(["--semestre", "inexistente", "--raiz-dados", tmp,
                          "--saida", tmp])
            solver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
