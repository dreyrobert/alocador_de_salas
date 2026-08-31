import tempfile
import unittest
from pathlib import Path

from lns_fix_and_optimize import (
    alocacoes_por_disciplina_horario,
    aplicar_start_e_fixacao_x,
    disciplinas_da_fase,
    disciplinas_do_curso,
    disciplinas_por_demanda,
    parse_solucao_x,
    pontuar_disciplinas_por_penalidade,
    vizinhanca_por_fase,
    vizinhanca_por_penalidade_atual,
)


class DisciplinaFake:
    def __init__(self, curso, fase, alunos, horarios, preferenciais=None):
        self.curso = curso
        self.fase = fase
        self.alunos = alunos
        self.salasPreferenciais = preferenciais or []
        self._horarios = horarios

    def max_alunos_agrupamento(self):
        return self.alunos

    def horarios_agrupamento(self):
        return {horario: object() for horario in self._horarios}


class VarFake:
    def __init__(self):
        self.Start = None
        self.LB = None
        self.UB = None


class TestLnsFixAndOptimize(unittest.TestCase):
    def test_parse_solucao_x_le_variaveis_do_arquivo_sol(self):
        conteudo = "\n".join(
            [
                "# Objective value = 10",
                "x[D1,101-A,Horario_2_1] 1",
                "x[D1,102-A,Horario_2_1] 0",
                "y[D1,101-A] 1",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo = Path(temp_dir) / "solution.sol"
            arquivo.write_text(conteudo, encoding="utf-8")

            solucao = parse_solucao_x(arquivo)

        self.assertEqual(solucao[("D1", "101-A", "Horario_2_1")], 1)
        self.assertEqual(solucao[("D1", "102-A", "Horario_2_1")], 0)
        self.assertNotIn(("D1", "101-A"), solucao)

    def test_alocacoes_por_disciplina_horario_filtra_valores_iguais_a_um(self):
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 0,
            ("D1", "102-A", "Horario_2_1"): 1,
            ("D2", "101-A", "Horario_2_1"): 1,
        }

        alocacoes = alocacoes_por_disciplina_horario(solucao)

        self.assertEqual(alocacoes[("D1", "Horario_2_1")], "102-A")
        self.assertEqual(alocacoes[("D2", "Horario_2_1")], "101-A")

    def test_seletores_de_disciplina_por_fase_curso_e_demanda(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 35, ["Horario_2_1"]),
            "D2": DisciplinaFake("CC", 3, 40, ["Horario_2_2"]),
            "D3": DisciplinaFake("ADM", 1, 51, ["Horario_3_1"]),
        }

        self.assertEqual(disciplinas_da_fase(disciplinas, "CC", "1"), {"D1"})
        self.assertEqual(disciplinas_do_curso(disciplinas, "CC"), {"D1", "D2"})
        self.assertEqual(disciplinas_por_demanda(disciplinas, 50, 2), {"D3"})

        vizinhanca = vizinhanca_por_fase(disciplinas, "CC", 1)

        self.assertEqual(vizinhanca.tipo, "fase")
        self.assertEqual(vizinhanca.recurso, "CC_1")
        self.assertEqual(vizinhanca.disciplinas, {"D1"})

    def test_pontua_penalidade_por_nao_preferencial_nao_alocada_e_multiplas_salas(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                30,
                ["Horario_2_1", "Horario_2_2"],
                ["101-A"],
            ),
            "D2": DisciplinaFake("ADM", 1, 30, ["Horario_3_1"], ["201-B"]),
        }
        solucao = {
            ("D1", "102-A", "Horario_2_1"): 1,
            ("D1", "103-A", "Horario_2_2"): 1,
        }

        ranking = pontuar_disciplinas_por_penalidade(disciplinas, solucao)
        por_disciplina = {linha["disciplina"]: linha for linha in ranking}

        self.assertEqual(por_disciplina["D1"]["alocacoes_nao_preferenciais"], 2)
        self.assertEqual(por_disciplina["D1"]["salas_usadas_qtd"], 2)
        self.assertEqual(por_disciplina["D1"]["penalidade_proxy"], 550)
        self.assertEqual(por_disciplina["D2"]["horarios_nao_alocados"], 1)
        self.assertGreater(
            por_disciplina["D2"]["penalidade_proxy"],
            por_disciplina["D1"]["penalidade_proxy"],
        )

    def test_vizinhanca_por_penalidade_atual_libera_top_n_com_penalidade(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"], ["101-A"]),
            "D2": DisciplinaFake("ADM", 1, 30, ["Horario_3_1"], ["201-B"]),
            "D3": DisciplinaFake("CC", 3, 20, ["Horario_4_1"], ["301-A"]),
        }
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D2", "202-B", "Horario_3_1"): 1,
        }

        vizinhanca = vizinhanca_por_penalidade_atual(disciplinas, solucao, top_n=1)

        self.assertEqual(vizinhanca.tipo, "penalidade_atual")
        self.assertEqual(vizinhanca.disciplinas, {"D3"})

    def test_aplica_start_e_fixa_variaveis_fora_da_vizinhanca(self):
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): VarFake(),
            ("D2", "102-A", "Horario_2_1"): VarFake(),
            ("D3", "103-A", "Horario_2_1"): VarFake(),
        }
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D2", "102-A", "Horario_2_1"): 0,
        }

        resumo = aplicar_start_e_fixacao_x(x_vars, solucao, {"D1"})

        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].Start, 1)
        self.assertIsNone(x_vars[("D1", "101-A", "Horario_2_1")].LB)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].UB, 0)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].Start, 0)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].LB, 0)
        self.assertEqual(resumo["variaveis_x_livres"], 1)
        self.assertEqual(resumo["variaveis_x_fixadas"], 2)
        self.assertEqual(resumo["chaves_sem_valor_incumbente"], 1)


if __name__ == "__main__":
    unittest.main()
