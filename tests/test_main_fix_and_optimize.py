import tempfile
import unittest
from pathlib import Path

from main_fix_and_optimize import (
    gerar_primeira_solucao,
    parametros_primeira_solucao,
    parametros_subproblema,
    reotimizar_vizinhanca_curso,
)


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

    def test_reotimizar_vizinhanca_curso_libera_curso_e_usa_incumbente(self):
        chamadas = {"carregar": [], "ler_solucao": [], "construir": [], "resolver": []}

        def carregar_fake(*args):
            chamadas["carregar"].append(args)
            return "instancia"

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
        self.assertEqual(
            chamadas["carregar"],
            [("horarios.xlsx", "salas.csv", "preferenciais.xlsx")],
        )
        self.assertEqual(chamadas["ler_solucao"], ["incumbente.sol"])
        self.assertEqual(len(chamadas["construir"]), 1)
        instancia, kwargs_construir = chamadas["construir"][0]
        self.assertEqual(instancia, "instancia")
        self.assertEqual(
            kwargs_construir["solucao_incumbente_x"],
            {("D1", "101-A", "Horario_2_1"): 1},
        )
        self.assertEqual(kwargs_construir["curso_livre"], "CC")
        self.assertEqual(len(chamadas["resolver"]), 1)
        modelo_alocacao, kwargs_resolver = chamadas["resolver"][0]
        self.assertEqual(modelo_alocacao, "modelo")
        self.assertEqual(kwargs_resolver["parametros_gurobi"], parametros_subproblema())
        self.assertEqual(kwargs_resolver["arquivo_solucao"], str(arquivo_saida))


if __name__ == "__main__":
    unittest.main()
