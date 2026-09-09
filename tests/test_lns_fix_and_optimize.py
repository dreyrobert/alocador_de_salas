import tempfile
import unittest
from pathlib import Path

from lns_fix_and_optimize import (
    aplicar_start_e_fixacao_x,
    aplicar_start_x,
    cursos_da_instancia,
    disciplinas_da_fase,
    disciplinas_do_curso,
    extrair_solucao_x,
    fixar_fora_da_vizinhanca_x,
    liberar_fixacoes_x,
    parse_objetivo_sol,
    parse_solucao_x,
    preparar_fixacao_vizinhanca_x,
    salvar_historico_csv,
    salvar_solucao_x,
    solucao_melhorou,
    vizinhanca_por_curso,
)


class DisciplinaFake:
    def __init__(self, curso, fase):
        self.curso = curso
        self.fase = fase


class VarFake:
    def __init__(self, x=None):
        self.X = x
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

    def test_extrair_solucao_x_le_variaveis_em_memoria(self):
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): VarFake(1.0),
            ("D1", "102-A", "Horario_2_1"): VarFake(0.0),
            ("D2", "101-A", "Horario_2_2"): VarFake(0.999999),
        }

        solucao = extrair_solucao_x(x_vars)

        self.assertEqual(
            solucao,
            {
                ("D1", "101-A", "Horario_2_1"): 1,
                ("D1", "102-A", "Horario_2_1"): 0,
                ("D2", "101-A", "Horario_2_2"): 1,
            },
        )

    def test_salvar_solucao_x_grava_formato_parseavel(self):
        solucao_x = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D1", "102-A", "Horario_2_1"): 0,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "melhor.sol"
            salvar_solucao_x(solucao_x, caminho, objetivo=123.5)

            self.assertEqual(parse_objetivo_sol(caminho), 123.5)
            self.assertEqual(parse_solucao_x(caminho), solucao_x)

    def test_seletores_de_disciplina_por_fase_e_curso(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1),
            "D2": DisciplinaFake("CC", 3),
            "D3": DisciplinaFake("ADM", 1),
        }

        self.assertEqual(disciplinas_da_fase(disciplinas, "CC", "1"), {"D1"})
        self.assertEqual(disciplinas_do_curso(disciplinas, "CC"), {"D1", "D2"})

    def test_vizinhanca_por_curso_libera_disciplinas_do_curso(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1),
            "D2": DisciplinaFake("CC", 3),
            "D3": DisciplinaFake("ADM", 1),
        }

        vizinhanca = vizinhanca_por_curso(disciplinas, "CC")

        self.assertEqual(vizinhanca.tipo, "curso")
        self.assertEqual(vizinhanca.recurso, "CC")
        self.assertEqual(vizinhanca.disciplinas_liberadas, frozenset({"D1", "D2"}))

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

    def test_helpers_aplicam_start_fixam_liberam_e_refixam_x(self):
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): VarFake(),
            ("D2", "102-A", "Horario_2_1"): VarFake(),
            ("D3", "103-A", "Horario_2_1"): VarFake(),
        }
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D2", "102-A", "Horario_2_1"): 0,
            ("D3", "103-A", "Horario_2_1"): 1,
        }

        resumo_start = aplicar_start_x(x_vars, solucao)
        chaves_fixadas_cc, resumo_fixacao_cc = fixar_fora_da_vizinhanca_x(
            x_vars,
            solucao,
            {"D1"},
        )

        self.assertEqual(resumo_start["valores_start_definidos"], 3)
        self.assertEqual(chaves_fixadas_cc, {
            ("D2", "102-A", "Horario_2_1"),
            ("D3", "103-A", "Horario_2_1"),
        })
        self.assertIsNone(x_vars[("D1", "101-A", "Horario_2_1")].LB)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].UB, 1)
        self.assertEqual(resumo_fixacao_cc["variaveis_x_livres"], 1)
        self.assertEqual(resumo_fixacao_cc["variaveis_x_fixadas"], 2)

        liberadas = liberar_fixacoes_x(x_vars, chaves_fixadas_cc)

        self.assertEqual(liberadas, 2)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].UB, 1)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].UB, 1)

        chaves_fixadas_adm, _ = fixar_fora_da_vizinhanca_x(
            x_vars,
            solucao,
            {"D2"},
        )

        self.assertEqual(chaves_fixadas_adm, {
            ("D1", "101-A", "Horario_2_1"),
            ("D3", "103-A", "Horario_2_1"),
        })
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].LB, 1)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].UB, 1)

    def test_preparar_fixacao_vizinhanca_x_libera_anteriores_e_retorna_novas(self):
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): VarFake(),
            ("D2", "102-A", "Horario_2_1"): VarFake(),
            ("D3", "103-A", "Horario_2_1"): VarFake(),
        }
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D2", "102-A", "Horario_2_1"): 0,
            ("D3", "103-A", "Horario_2_1"): 1,
        }

        chaves_fixadas_cc, resumo_cc = preparar_fixacao_vizinhanca_x(
            x_vars,
            solucao,
            {"D1"},
        )
        chaves_fixadas_adm, resumo_adm = preparar_fixacao_vizinhanca_x(
            x_vars,
            solucao,
            {"D2"},
            chaves_fixadas_anteriores=chaves_fixadas_cc,
        )

        self.assertEqual(resumo_cc["fixacoes_liberadas"], 0)
        self.assertEqual(resumo_adm["fixacoes_liberadas"], 2)
        self.assertEqual(chaves_fixadas_adm, {
            ("D1", "101-A", "Horario_2_1"),
            ("D3", "103-A", "Horario_2_1"),
        })
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].LB, 1)
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].UB, 1)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D2", "102-A", "Horario_2_1")].UB, 1)
        self.assertEqual(x_vars[("D3", "103-A", "Horario_2_1")].LB, 1)
        self.assertEqual(resumo_adm["variaveis_x_livres"], 1)
        self.assertEqual(resumo_adm["variaveis_x_fixadas"], 2)

    def test_parse_objetivo_sol_recupera_valor_do_cabecalho(self):
        conteudo = "# Objective value = 186294.5\nx[D1,101-A,Horario_2_1] 1\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "teste.sol"
            caminho.write_text(conteudo, encoding="utf-8")
            self.assertEqual(parse_objetivo_sol(caminho), 186294.5)

    def test_solucao_melhorou_valida_apenas_reducao_estrita_de_custo(self):
        atual = {"solucoes": 1, "objetivo": 100.0}
        candidata_melhor = {"solucoes": 1, "objetivo": 95.0}
        candidata_pior = {"solucoes": 1, "objetivo": 105.0}
        candidata_igual = {"solucoes": 1, "objetivo": 100.0}
        candidata_inviavel = {"solucoes": 0, "objetivo": None}

        self.assertTrue(solucao_melhorou(atual, candidata_melhor))
        self.assertFalse(solucao_melhorou(atual, candidata_pior))
        self.assertFalse(solucao_melhorou(atual, candidata_igual))
        self.assertFalse(solucao_melhorou(atual, candidata_inviavel))
        self.assertTrue(solucao_melhorou(None, candidata_melhor))

    def test_cursos_da_instancia_extrai_ordenado(self):
        class InstanciaComCursos:
            cursos = {"MED": object(), "CC": object(), "ADM": object()}

        self.assertEqual(cursos_da_instancia(InstanciaComCursos()), ["ADM", "CC", "MED"])

    def test_salvar_historico_csv_grava_arquivo(self):
        historico = [
            {"iteracao": 1, "curso": "CC", "melhorou": True, "objetivo": 100.0},
            {"iteracao": 2, "curso": "ADM", "melhorou": False, "objetivo": 100.0},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho = Path(temp_dir) / "historico.csv"
            salvar_historico_csv(historico, caminho)
            self.assertTrue(caminho.exists())
            conteudo = caminho.read_text(encoding="utf-8")
            self.assertIn("iteracao,curso,melhorou,objetivo", conteudo)
            self.assertIn("1,CC,True,100.0", conteudo)


if __name__ == "__main__":
    unittest.main()
