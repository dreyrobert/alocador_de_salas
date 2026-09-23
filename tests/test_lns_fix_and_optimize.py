import tempfile
import unittest
from pathlib import Path

from alocador_salas.domain.horario import Horario
from alocador_salas.optimization.lns_fix_and_optimize_compat import (
    aplicar_start_e_fixacao_x,
    disciplinas_da_fase,
)
from alocador_salas.optimization.lns_fix_and_optimize import (
    aplicar_start_x,
    cursos_da_instancia,
    disciplinas_do_dia_turno,
    disciplinas_do_curso,
    extrair_solucao_x,
    fixar_fora_da_vizinhanca_x,
    liberar_fixacoes_x,
    ordenar_cursos,
    parse_objetivo_sol,
    parse_solucao_x,
    preparar_fixacao_vizinhanca_x,
    salvar_historico_csv,
    salvar_solucao_x,
    solucao_melhorou,
    vizinhanca_por_curso,
    vizinhanca_por_dia_turno,
    vizinhancas_por_dia_turno,
)


class DisciplinaFake:
    def __init__(self, curso, fase, horarios=None, horarios_agrupados=None):
        self.curso = curso
        self.fase = fase
        self.horarios = horarios or {}
        self._horarios_agrupados = horarios_agrupados

    def horarios_agrupamento(self):
        if self._horarios_agrupados is not None:
            return self._horarios_agrupados
        return self.horarios


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

    def test_seleciona_disciplinas_com_aula_no_mesmo_dia_e_turno(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                {
                    "Horario_2_1": Horario(2, 1),
                    "Horario_4_13": Horario(4, 13),
                },
            ),
            "D2": DisciplinaFake("ADM", 3, {"Horario_2_6": Horario(2, 6)}),
            "D3": DisciplinaFake("MAT", 1, {"Horario_2_7": Horario(2, 7)}),
            "D4": DisciplinaFake("MED", 2, {"Horario_3_1": Horario(3, 1)}),
        }

        self.assertEqual(
            disciplinas_do_dia_turno(disciplinas, 2, "M"),
            {"D1", "D2"},
        )
        self.assertEqual(disciplinas_do_dia_turno(disciplinas, 4, "N"), {"D1"})

    def test_seletor_considera_horarios_de_disciplinas_agrupadas(self):
        disciplina = DisciplinaFake(
            "CC",
            1,
            horarios={"Horario_2_1": Horario(2, 1)},
            horarios_agrupados={
                "Horario_2_1": Horario(2, 1),
                "Horario_5_8": Horario(5, 8),
            },
        )

        selecionadas = disciplinas_do_dia_turno({"D1": disciplina}, 5, "T")

        self.assertEqual(selecionadas, {"D1"})

    def test_vizinhanca_por_dia_turno_libera_disciplinas_inteiras(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                {
                    "Horario_2_1": Horario(2, 1),
                    "Horario_4_13": Horario(4, 13),
                },
            ),
            "D2": DisciplinaFake("ADM", 1, {"Horario_3_1": Horario(3, 1)}),
        }

        vizinhanca = vizinhanca_por_dia_turno(disciplinas, 2, "M")

        self.assertEqual(vizinhanca.tipo, "dia_turno")
        self.assertEqual(vizinhanca.recurso, "2_M")
        self.assertEqual(vizinhanca.disciplinas_liberadas, frozenset({"D1"}))

    def test_seletor_rejeita_dia_e_turno_invalidos(self):
        with self.assertRaisesRegex(ValueError, "Dia de horario invalido"):
            disciplinas_do_dia_turno({}, 1, "M")
        with self.assertRaisesRegex(ValueError, "Turno invalido"):
            disciplinas_do_dia_turno({}, 2, "V")

    def test_gera_apenas_vizinhancas_dia_turno_existentes_em_ordem(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                {
                    "Horario_2_1": Horario(2, 1),
                    "Horario_4_13": Horario(4, 13),
                },
            ),
            "D2": DisciplinaFake("ADM", 1, {"Horario_2_8": Horario(2, 8)}),
            "D3": DisciplinaFake("MAT", 1, {"Horario_3_6": Horario(3, 6)}),
        }

        vizinhancas = vizinhancas_por_dia_turno(disciplinas)

        self.assertEqual(
            [vizinhanca.recurso for vizinhanca in vizinhancas],
            ["2_M", "2_T", "3_M", "4_N"],
        )
        self.assertEqual(
            [vizinhanca.disciplinas_liberadas for vizinhanca in vizinhancas],
            [
                frozenset({"D1"}),
                frozenset({"D2"}),
                frozenset({"D3"}),
                frozenset({"D1"}),
            ],
        )
        self.assertTrue(
            all(vizinhanca.tipo == "dia_turno" for vizinhanca in vizinhancas)
        )

    def test_nao_gera_vizinhancas_dia_turno_para_instancia_vazia(self):
        self.assertEqual(vizinhancas_por_dia_turno({}), [])

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

    def test_ordenar_cursos_alfabetica_preserva_baseline(self):
        cursos = ["MED", "CC", "ADM"]

        self.assertEqual(ordenar_cursos(cursos, {}, "alfabetica"), ["ADM", "CC", "MED"])

    def test_ordenar_cursos_maior_demanda_usa_qtd_disciplinas_e_alunos(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1),
            "D2": DisciplinaFake("CC", 3),
            "D3": DisciplinaFake("ADM", 1),
            "D4": DisciplinaFake("MED", 1),
            "D5": DisciplinaFake("MED", 2),
        }
        disciplinas["D1"].alunos = 30
        disciplinas["D2"].alunos = 20
        disciplinas["D3"].alunos = 80
        disciplinas["D4"].alunos = 40
        disciplinas["D5"].alunos = 50

        self.assertEqual(
            ordenar_cursos(["ADM", "CC", "MED"], disciplinas, "maior-demanda"),
            ["MED", "CC", "ADM"],
        )

    def test_ordenar_cursos_aleatoria_e_reprodutivel_com_seed(self):
        cursos = ["ADM", "CC", "MED", "MAT"]

        ordem_1 = ordenar_cursos(cursos, {}, "aleatoria", seed=42)
        ordem_2 = ordenar_cursos(reversed(cursos), {}, "aleatoria", seed=42)

        self.assertEqual(ordem_1, ordem_2)
        self.assertEqual(sorted(ordem_1), ["ADM", "CC", "MAT", "MED"])

    def test_ordenar_cursos_aleatoria_exige_seed(self):
        with self.assertRaisesRegex(ValueError, "exige seed"):
            ordenar_cursos(["ADM", "CC"], {}, "aleatoria")

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
