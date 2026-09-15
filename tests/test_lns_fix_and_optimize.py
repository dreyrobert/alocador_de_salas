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
    bloqueadores_das_disciplinas,
    calcular_penalidades_disciplinas,
    cursos_da_instancia,
    disciplinas_do_dia_turno,
    disciplinas_do_curso,
    extrair_solucao_x,
    fixar_fora_da_vizinhanca_x,
    liberar_fixacoes_x,
    parse_objetivo_sol,
    parse_solucao_x,
    preparar_fixacao_vizinhanca_x,
    salvar_historico_csv,
    salvar_solucao_x,
    salas_candidatas_para_disciplina,
    solucao_melhorou,
    vizinhanca_por_curso,
    vizinhanca_por_dia_turno,
    vizinhancas_por_dia_turno,
    vizinhanca_penalidade_bloqueadores,
)


class DisciplinaFake:
    def __init__(self, curso, fase, horarios=None, horarios_agrupados=None):
        self.curso = curso
        self.fase = fase
        self.alunos = 30
        self.salasPreferenciais = []
        self.horarios = horarios or {}
        self._horarios_agrupados = horarios_agrupados

    def horarios_agrupamento(self):
        if self._horarios_agrupados is not None:
            return self._horarios_agrupados
        return self.horarios

    def max_alunos_agrupamento(self):
        return self.alunos


class VarFake:
    def __init__(self, x=None):
        self.X = x
        self.Start = None
        self.LB = None
        self.UB = None


class SalaFake:
    def __init__(self, capacidade):
        self.capacidade = capacidade


class InstanciaVizinhancaFake:
    def __init__(self, disciplinas, salas, matriz_dist=None):
        self.disciplinas = disciplinas
        self.salas = salas
        self.salas_lista = list(salas)
        tamanho = len(salas)
        self.matriz_dist = matriz_dist or [
            [abs(i - j) for j in range(tamanho)] for i in range(tamanho)
        ]


class TestLnsFixAndOptimize(unittest.TestCase):
    def test_penalidade_prioriza_nao_alocada_e_sala_nao_preferencial(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, {"Horario_2_1": Horario(2, 1)}),
            "D2": DisciplinaFake("CC", 1, {"Horario_2_2": Horario(2, 2)}),
        }
        disciplinas["D1"].salasPreferenciais = ["A"]
        disciplinas["D2"].salasPreferenciais = ["A"]
        instancia = InstanciaVizinhancaFake(
            disciplinas, {"A": SalaFake(50), "B": SalaFake(50)}
        )
        solucao = {("D2", "B", "Horario_2_2"): 1}

        ranking = calcular_penalidades_disciplinas(instancia, solucao)

        self.assertEqual([item.disciplina for item in ranking], ["D1", "D2"])
        self.assertEqual(ranking[0].horarios_nao_alocados, 1)
        self.assertEqual(ranking[1].alocacoes_nao_preferenciais, 1)

    def test_salas_candidatas_respeitam_capacidade_e_preferencia(self):
        disciplina = DisciplinaFake("CC", 1, {"Horario_2_1": Horario(2, 1)})
        disciplina.alunos = 40
        disciplina.salasPreferenciais = ["P"]
        instancia = InstanciaVizinhancaFake(
            {"D1": disciplina},
            {"PEQUENA": SalaFake(20), "N": SalaFake(50), "P": SalaFake(40)},
        )

        candidatas = salas_candidatas_para_disciplina(instancia, {}, "D1", 2)

        self.assertEqual(candidatas, ["P", "N"])

    def test_bloqueadores_ocupam_sala_candidata_no_mesmo_horario(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, {"Horario_2_1": Horario(2, 1)}),
            "D2": DisciplinaFake("ADM", 1, {"Horario_2_1": Horario(2, 1)}),
            "D3": DisciplinaFake("ADM", 1, {"Horario_2_2": Horario(2, 2)}),
        }
        for disciplina in disciplinas.values():
            disciplina.alunos = 30
        disciplinas["D1"].salasPreferenciais = ["A"]
        instancia = InstanciaVizinhancaFake(
            disciplinas, {"A": SalaFake(50), "B": SalaFake(50)}
        )
        solucao = {
            ("D2", "A", "Horario_2_1"): 1,
            ("D3", "A", "Horario_2_2"): 1,
        }

        bloqueadores, relevancia = bloqueadores_das_disciplinas(
            instancia, solucao, {"D1"}, max_salas_candidatas=1
        )

        self.assertEqual(bloqueadores, {"D2"})
        self.assertEqual(relevancia["D2"], 1)

    def test_vizinhanca_inclui_semente_e_bloqueador_e_respeita_orcamento(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, {"Horario_2_1": Horario(2, 1)}),
            "D2": DisciplinaFake("ADM", 1, {"Horario_2_1": Horario(2, 1)}),
            "D3": DisciplinaFake("MAT", 1, {"Horario_3_1": Horario(3, 1)}),
        }
        for disciplina in disciplinas.values():
            disciplina.alunos = 30
            disciplina.salasPreferenciais = ["A"]
        instancia = InstanciaVizinhancaFake(
            disciplinas, {"A": SalaFake(50), "B": SalaFake(50)}
        )
        solucao = {
            ("D2", "A", "Horario_2_1"): 1,
            ("D3", "B", "Horario_3_1"): 1,
        }

        vizinhanca = vizinhanca_penalidade_bloqueadores(
            instancia,
            solucao,
            sementes_por_vizinhanca=1,
            max_salas_candidatas=1,
            percentual_x_maximo=0.8,
        )

        self.assertIsNotNone(vizinhanca)
        self.assertEqual(vizinhanca.tipo, "penalidade_bloqueadores")
        self.assertEqual(vizinhanca.disciplinas_liberadas, frozenset({"D1", "D2"}))
        self.assertLessEqual(vizinhanca.metadados["percentual_x_estimado"], 0.8)

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
