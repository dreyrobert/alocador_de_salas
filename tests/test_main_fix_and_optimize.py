import tempfile
import unittest
from pathlib import Path

from lns_fix_and_optimize import Vizinhanca
from main_fix_and_optimize import (
    executar_fix_and_optimize_cursos,
    executar_passada_por_cursos,
    gerar_primeira_solucao,
    parametros_primeira_solucao,
    parametros_subproblema,
    reotimizar_subproblema,
    reotimizar_vizinhanca_curso,
)


class InstanciaFake:
    def __init__(self, disciplinas):
        self.disciplinas = disciplinas
        self.salas = {}
        self.salas_lista = []
        self.matriz_dist = []
        self.horarios = {}
        self.fases = {}
        self.cursos = {}


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


class TestMainFixAndOptimize(unittest.TestCase):
    def test_parametros_primeira_solucao_usa_limites_de_300s_por_padrao(self):
        self.assertEqual(
            parametros_primeira_solucao(),
            {
                "TimeLimit": 300,
                "MIPFocus": 1,
                "NoRelHeurTime": 300,
            },
        )

    def test_parametros_subproblema_usa_limite_de_300s_por_padrao(self):
        self.assertEqual(
            parametros_subproblema(),
            {
                "TimeLimit": 300,
                "MIPFocus": 1,
            },
        )

    def test_gerar_primeira_solucao_chama_modelo_existente_com_parametros_heuristicos(self):
        chamadas = {"carregar": [], "construir": [], "resolver": []}

        def carregar_fake(*args):
            chamadas["carregar"].append(args)
            return "instancia"

        def construir_fake(instancia):
            chamadas["construir"].append(instancia)
            return "modelo"

        def resolver_fake(modelo_alocacao, parametros_gurobi=None, arquivo_solucao=None):
            chamadas["resolver"].append(
                (
                    modelo_alocacao,
                    {
                        "parametros_gurobi": parametros_gurobi,
                        "arquivo_solucao": arquivo_solucao,
                    },
                )
            )
            return {
                "status_nome": "TIME_LIMIT",
                "solucoes": 1,
                "arquivo_solucao": arquivo_solucao,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo_solucao = Path(temp_dir) / "subdir" / "primeira.sol"

            resultado = gerar_primeira_solucao(
                arquivo_horarios="horarios.xlsx",
                arquivo_salas="salas.csv",
                arquivo_salas_preferenciais="preferenciais.xlsx",
                arquivo_solucao=str(arquivo_solucao),
                carregar=carregar_fake,
                construir=construir_fake,
                resolver=resolver_fake,
            )

        self.assertEqual(resultado["etapa"], "primeira_solucao")
        self.assertEqual(
            chamadas["carregar"],
            [("horarios.xlsx", "salas.csv", "preferenciais.xlsx")],
        )
        self.assertEqual(chamadas["construir"], ["instancia"])
        self.assertEqual(len(chamadas["resolver"]), 1)
        modelo_alocacao, kwargs_resolver = chamadas["resolver"][0]
        self.assertEqual(modelo_alocacao, "modelo")
        self.assertEqual(kwargs_resolver["parametros_gurobi"], parametros_primeira_solucao())
        self.assertEqual(kwargs_resolver["arquivo_solucao"], str(arquivo_solucao))

    def test_reotimizar_subproblema_com_objeto_vizinhanca_generico(self):
        chamadas = {"construir": [], "resolver": []}

        def construir_fake(instancia, **kwargs):
            chamadas["construir"].append((instancia, kwargs))
            return "modelo"

        def resolver_fake(modelo_alocacao, parametros_gurobi=None, arquivo_solucao=None):
            chamadas["resolver"].append((modelo_alocacao, parametros_gurobi, arquivo_solucao))
            return {"status_nome": "OPTIMAL", "objetivo": 120.0}

        viz = Vizinhanca(
            tipo="curso",
            recurso="CC",
            disciplinas_liberadas=frozenset({"D1", "D2"}),
        )
        solucao_dict = {("D1", "101-A", "Horario_2_1"): 1}

        resultado = reotimizar_subproblema(
            arquivo_solucao_incumbente=solucao_dict,
            disciplinas_livres=viz,
            instancia="instancia_pre_carregada",
            arquivo_solucao=None,
            tempo_subproblema=60,
            construir=construir_fake,
            resolver=resolver_fake,
        )

        self.assertEqual(resultado["etapa"], "reotimizacao_subproblema")
        self.assertEqual(resultado["tipo_vizinhanca"], "curso")
        self.assertEqual(resultado["recurso"], "CC")
        self.assertEqual(resultado["disciplinas_livres_qtd"], 2)
        self.assertEqual(len(chamadas["construir"]), 1)
        inst, kwargs_construir = chamadas["construir"][0]
        self.assertEqual(inst, "instancia_pre_carregada")
        self.assertEqual(kwargs_construir["solucao_incumbente_x"], solucao_dict)
        self.assertEqual(kwargs_construir["disciplinas_livres"], {"D1", "D2"})

    def test_reotimizar_vizinhanca_curso_libera_disciplinas_do_curso_e_usa_incumbente(self):
        chamadas = {"carregar": [], "ler_solucao": [], "construir": [], "resolver": []}

        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
            "D2": DisciplinaFake("ADM", 1, 30, ["Horario_2_1"]),
        }
        instancia_mock = InstanciaFake(disciplinas)

        def carregar_fake(*args):
            chamadas["carregar"].append(args)
            return instancia_mock

        def ler_solucao_fake(arquivo):
            chamadas["ler_solucao"].append(arquivo)
            return {("D1", "101-A", "Horario_2_1"): 1}

        def construir_fake(instancia, **kwargs):
            chamadas["construir"].append((instancia, kwargs))
            return "modelo"

        def resolver_fake(modelo_alocacao, parametros_gurobi=None, arquivo_solucao=None):
            chamadas["resolver"].append(
                (
                    modelo_alocacao,
                    {
                        "parametros_gurobi": parametros_gurobi,
                        "arquivo_solucao": arquivo_solucao,
                    },
                )
            )
            return {
                "status_nome": "TIME_LIMIT",
                "solucoes": 1,
                "lns": {"variaveis_x_livres": 10, "variaveis_x_fixadas": 90},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo_saida = Path(temp_dir) / "cc.sol"

            resultado = reotimizar_vizinhanca_curso(
                arquivo_solucao_incumbente="incumbente.sol",
                curso_livre="CC",
                arquivo_horarios="horarios.xlsx",
                arquivo_salas="salas.csv",
                arquivo_salas_preferenciais="preferenciais.xlsx",
                arquivo_solucao=str(arquivo_saida),
                carregar=carregar_fake,
                construir=construir_fake,
                resolver=resolver_fake,
                ler_solucao=ler_solucao_fake,
            )

        self.assertEqual(resultado["etapa"], "reotimizacao_curso")
        self.assertEqual(resultado["curso_livre"], "CC")
        self.assertEqual(resultado["tipo_vizinhanca"], "curso")
        self.assertEqual(resultado["disciplinas_livres_qtd"], 1)
        self.assertEqual(
            chamadas["carregar"],
            [("horarios.xlsx", "salas.csv", "preferenciais.xlsx")],
        )
        self.assertEqual(chamadas["ler_solucao"], ["incumbente.sol"])
        self.assertEqual(len(chamadas["construir"]), 1)
        instancia, kwargs_construir = chamadas["construir"][0]
        self.assertEqual(instancia, instancia_mock)
        self.assertEqual(
            kwargs_construir["solucao_incumbente_x"],
            {("D1", "101-A", "Horario_2_1"): 1},
        )
        self.assertEqual(kwargs_construir["disciplinas_livres"], {"D1"})
        self.assertEqual(len(chamadas["resolver"]), 1)
        modelo_alocacao, kwargs_resolver = chamadas["resolver"][0]
        self.assertEqual(modelo_alocacao, "modelo")
        self.assertEqual(kwargs_resolver["parametros_gurobi"], parametros_subproblema())
        self.assertEqual(kwargs_resolver["arquivo_solucao"], str(arquivo_saida))

    def test_reotimizar_subproblema_valida_vizinhanca_vazia(self):
        with self.assertRaises(ValueError):
            reotimizar_subproblema(
                arquivo_solucao_incumbente={},
                disciplinas_livres=[],
                instancia=InstanciaFake({}),
            )

    def test_executar_passada_por_cursos_aceita_melhoria_e_atualiza_incumbente(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
            "D2": DisciplinaFake("ADM", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object(), "ADM": object()}

        with tempfile.TemporaryDirectory() as temp_dir:
            incumbente_sol = Path(temp_dir) / "primeira.sol"
            incumbente_sol.write_text("# Objective value = 200.0\nx[D1,101-A,Horario_2_1] 1\n", encoding="utf-8")
            melhor_sol = Path(temp_dir) / "melhor.sol"

            def construir_fake(inst, **kwargs):
                return "modelo"

            # CC melhora (180.0), ADM nao melhora (190.0 > 180.0)
            objetivos = {"CC": 180.0, "ADM": 190.0}

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                # Extrai o curso a partir do arquivo_solucao
                curso = "CC" if "CC" in arquivo_solucao else "ADM"
                obj = objetivos[curso]
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text(f"# Objective value = {obj}\n", encoding="utf-8")
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": obj,
                    "arquivo_solucao": arquivo_solucao,
                    "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
                }

            incumbente, historico = executar_passada_por_cursos(
                arquivo_solucao_incumbente=incumbente_sol,
                instancia=instancia,
                cursos=["CC", "ADM"],
                arquivo_melhor_solucao=melhor_sol,
                pasta_candidatos=Path(temp_dir) / "candidatos",
                tempo_subproblema=10,
                construir=construir_fake,
                resolver=resolver_fake,
                ler_solucao=lambda arq: {("D1", "101-A", "Horario_2_1"): 1},
            )

            self.assertEqual(incumbente["objetivo"], 180.0)
            self.assertEqual(len(historico), 2)
            self.assertTrue(historico[0]["melhorou"])
            self.assertEqual(historico[0]["curso"], "CC")
            self.assertFalse(historico[1]["melhorou"])
            self.assertEqual(historico[1]["curso"], "ADM")
            self.assertTrue(melhor_sol.exists())

    def test_executar_fix_and_optimize_cursos_loop_completo(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object()}

        with tempfile.TemporaryDirectory() as temp_dir:
            incumbente_sol = Path(temp_dir) / "inicial.sol"
            incumbente_sol.write_text("# Objective value = 300.0\nx[D1,101-A,Horario_2_1] 1\n", encoding="utf-8")
            melhor_sol = Path(temp_dir) / "melhor.sol"
            log_csv = Path(temp_dir) / "log.csv"
            log_json = Path(temp_dir) / "log.json"

            def carregar_fake(*args):
                return instancia

            def construir_fake(inst, **kwargs):
                return "modelo"

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text("# Objective value = 250.0\n", encoding="utf-8")
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": 250.0,
                    "arquivo_solucao": arquivo_solucao,
                    "lns": {"variaveis_x_livres": 10, "variaveis_x_fixadas": 90},
                }

            resultado = executar_fix_and_optimize_cursos(
                arquivo_solucao_incumbente=str(incumbente_sol),
                arquivo_melhor_solucao=str(melhor_sol),
                arquivo_log_csv=str(log_csv),
                arquivo_log_json=str(log_json),
                max_passadas=2,
                tempo_subproblema=5,
                carregar=carregar_fake,
                construir=construir_fake,
                resolver=resolver_fake,
                ler_solucao=lambda arq: {("D1", "101-A", "Horario_2_1"): 1},
            )

            self.assertEqual(resultado["etapa"], "fix_and_optimize_cursos")
            self.assertEqual(resultado["status"], "CONCLUIDO")
            self.assertEqual(resultado["objetivo_inicial"], 300.0)
            self.assertEqual(resultado["objetivo_final"], 250.0)
            self.assertEqual(resultado["ganho_absoluto"], 50.0)
            self.assertEqual(resultado["melhorias_aceitas"], 1)
            self.assertTrue(log_csv.exists())
            self.assertTrue(log_json.exists())


if __name__ == "__main__":
    unittest.main()

