import csv
import json
import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import patch

from alocador_salas.domain.horario import Horario
from alocador_salas.optimization.lns_fix_and_optimize import Vizinhanca
from alocador_salas.optimization.main_fix_and_optimize import (
    executar_fix_and_optimize,
    executar_fix_and_optimize_cursos,
    executar_passada_por_cursos,
    executar_passada_por_dia_turno,
    parametros_primeira_solucao,
    parametros_subproblema,
    reotimizar_vizinhanca,
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
        return {
            horario: (
                valor
                if isinstance(valor, Horario)
                else object()
            )
            for horario, valor in (
                self._horarios.items()
                if isinstance(self._horarios, dict)
                else ((horario, None) for horario in self._horarios)
            )
        }


class TestMainFixAndOptimize(unittest.TestCase):
    def executar_curso_pares_fake(self, objetivos, **opcoes):
        instancia = InstanciaFake({
            "A1": DisciplinaFake("ADM", 1, 30, ["Horario_2_1"]),
            "C1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
            "C2": DisciplinaFake("CC", 2, 30, ["Horario_3_1"]),
            "E1": DisciplinaFake("ENF", 1, 30, ["Horario_2_1"]),
        })
        instancia.cursos = {curso: object() for curso in ("ADM", "CC", "ENF")}
        objetivos = iter(objetivos)
        preparacoes, solucoes, limites = [], [], []
        relogio = [0.0]
        encerrar_apos = opcoes.pop("encerrar_apos", None)

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            objetivo = next(objetivos)
            solucao = {("A1", f"sala_{len(solucoes)}", "Horario_2_1"): 1}
            solucoes.append(solucao)
            limites.append(parametros_gurobi["TimeLimit"])
            if encerrar_apos == len(solucoes):
                relogio[0] = 11.0
            return {"status_nome": "OPTIMAL", "solucoes": 1,
                    "objetivo": objetivo, "solucao_x": solucao}

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "alocador_salas.optimization.main_fix_and_optimize.time.time",
            side_effect=lambda: relogio[0],
        ):
            resultado = executar_fix_and_optimize(
                tipo_vizinhanca="curso_pares",
                arquivo_melhor_solucao=str(Path(temp_dir) / "melhor.sol"),
                arquivo_log_csv=str(Path(temp_dir) / "log.csv"),
                arquivo_log_json=str(Path(temp_dir) / "log.json"),
                carregar=lambda *args: instancia,
                construir=lambda inst: "modelo",
                preparar_modelo=lambda modelo, **kwargs: preparacoes.append(kwargs),
                liberar_modelo=lambda modelo: None,
                resolver=resolver_fake,
                **opcoes,
            )
            with (Path(temp_dir) / "log.csv").open() as arquivo:
                registros_csv = list(csv.DictReader(arquivo))
            self.assertEqual(len(registros_csv), len(resultado["historico"]))
            for registro in registros_csv:
                if registro["vizinhanca"] == "par_cursos":
                    self.assertTrue(registro["curso_a"])
                    self.assertTrue(registro["curso_b"])
            dados = json.loads((Path(temp_dir) / "log.json").read_text())
            self.assertEqual(dados["historico"], resultado["historico"])
        return resultado, preparacoes, solucoes, limites

    def test_curso_pares_so_transita_apos_passada_inteira_sem_melhoria(self):
        resultado, preparacoes, solucoes, _ = self.executar_curso_pares_fake([
            100, 100, 90, 90, 90, 90, 80, 80, 80, 80, 70, 75, 60,
        ])
        historico = resultado["historico"]
        self.assertEqual([r["vizinhanca"] for r in historico], ["curso"] * 9 + ["par_cursos"] * 3)
        self.assertEqual([r["passada"] for r in historico], [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3)
        self.assertEqual([r["recurso"] for r in historico[-3:]], ["ADM+CC", "ADM+ENF", "CC+ENF"])
        self.assertEqual([p["disciplinas_livres"] for p in preparacoes[-3:]],
                         [{"A1", "C1", "C2"}, {"A1", "E1"}, {"C1", "C2", "E1"}])
        self.assertIs(preparacoes[9]["solucao_incumbente_x"], solucoes[6])
        self.assertIs(preparacoes[10]["solucao_incumbente_x"], solucoes[10])
        self.assertIs(preparacoes[11]["solucao_incumbente_x"], solucoes[10])
        self.assertEqual(resultado["objetivo_final"], 60)
        self.assertEqual(resultado["passadas_executadas"], 4)

    def test_curso_pares_pode_transitar_apos_primeira_passada(self):
        resultado, _, _, _ = self.executar_curso_pares_fake([100] * 7)
        self.assertEqual([r["vizinhanca"] for r in resultado["historico"]], ["curso"] * 3 + ["par_cursos"] * 3)

    def test_curso_pares_respeita_ordem_configurada(self):
        resultado, _, _, _ = self.executar_curso_pares_fake([100] * 7, ordem_cursos="maior-demanda")
        self.assertEqual([r["recurso"] for r in resultado["historico"]],
                         ["CC", "ADM", "ENF", "CC+ADM", "CC+ENF", "ADM+ENF"])

    def test_curso_pares_apenas_uma_passada_nao_inicia_pares(self):
        resultado, _, _, _ = self.executar_curso_pares_fake([100] * 4, apenas_uma_passada=True)
        self.assertEqual(resultado["passadas_executadas"], 1)
        self.assertTrue(all(r["vizinhanca"] == "curso" for r in resultado["historico"]))

    def test_curso_pares_respeita_tempo_total_nas_duas_fases(self):
        for quantidade in (2, 5):
            with self.subTest(chamadas=quantidade):
                resultado, _, _, limites = self.executar_curso_pares_fake(
                    [100] * quantidade, encerrar_apos=quantidade,
                    tempo_total_maximo=10, tempo_subproblema=60,
                )
                self.assertEqual(resultado["total_iteracoes"], quantidade - 1)
                self.assertTrue(all(limite == 10 for limite in limites[1:]))

    def test_parametros_primeira_solucao_usa_limites_de_300s_por_padrao(self):
        self.assertEqual(
            parametros_primeira_solucao(),
            {
                "TimeLimit": 300,
                "MIPFocus": 1,
                "NoRelHeurTime": 300,
            },
        )

    def test_parametros_subproblema_usa_limite_padrao_e_desativa_norel(self):
        self.assertEqual(
            parametros_subproblema(),
            {
                "TimeLimit": 300,
                "MIPFocus": 1,
                "NoRelHeurTime": 0,
            },
        )

    def test_reotimizar_vizinhanca_usa_objeto_vizinhanca_generico(self):
        chamadas = {"preparar": [], "resolver": []}
        vizinhanca = Vizinhanca(
            tipo="curso",
            recurso="CC",
            disciplinas_liberadas=frozenset({"D1", "D2"}),
        )
        solucao_incumbente = {("D1", "101-A", "Horario_2_1"): 1}

        def preparar_fake(modelo_alocacao, **kwargs):
            chamadas["preparar"].append((modelo_alocacao, kwargs))

        def resolver_fake(modelo_alocacao, parametros_gurobi=None, arquivo_solucao=None):
            chamadas["resolver"].append((modelo_alocacao, parametros_gurobi, arquivo_solucao))
            return {"status_nome": "OPTIMAL", "objetivo": 120.0}

        resultado = reotimizar_vizinhanca(
            modelo_alocacao="modelo",
            solucao_incumbente_x=solucao_incumbente,
            vizinhanca=vizinhanca,
            tempo_subproblema=60,
            arquivo_solucao=None,
            preparar_modelo=preparar_fake,
            resolver=resolver_fake,
        )

        self.assertEqual(resultado["etapa"], "reotimizacao_vizinhanca")
        self.assertEqual(resultado["tipo_vizinhanca"], "curso")
        self.assertEqual(resultado["recurso"], "CC")
        self.assertEqual(resultado["disciplinas_livres_qtd"], 2)
        self.assertEqual(chamadas["preparar"][0][0], "modelo")
        self.assertEqual(chamadas["preparar"][0][1]["solucao_incumbente_x"], solucao_incumbente)
        self.assertEqual(chamadas["preparar"][0][1]["disciplinas_livres"], {"D1", "D2"})
        self.assertEqual(chamadas["resolver"][0][1], parametros_subproblema(60))
        self.assertEqual(chamadas["resolver"][0][0], "modelo")

    def test_executar_passada_por_cursos_aceita_melhoria_e_atualiza_incumbente(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
            "D2": DisciplinaFake("ADM", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object(), "ADM": object()}

        with tempfile.TemporaryDirectory() as temp_dir:
            def construir_fake(inst, **kwargs):
                return "modelo"

            preparacoes = []

            def preparar_fake(modelo, **kwargs):
                self.assertEqual(modelo, "modelo")
                preparacoes.append(kwargs)

            # CC melhora (180.0), ADM nao melhora (190.0 > 180.0)
            objetivos = {"CC": 180.0, "ADM": 190.0}
            chamadas = []

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                curso = ["CC", "ADM"][len(chamadas)]
                chamadas.append((curso, arquivo_solucao))
                obj = objetivos[curso]
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text(f"# Objective value = {obj}\n", encoding="utf-8")
                return {
                    "status_nome": "OPTIMAL",
                    "tempo_solver_s": 7.346,
                    "solucoes": 1,
                    "objetivo": obj,
                    "arquivo_solucao": arquivo_solucao,
                    "solucao_x": {("D1", "101-A", "Horario_2_1"): 1 if curso == "CC" else 0},
                    "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
                }

            incumbente, historico = executar_passada_por_cursos(
                solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 0},
                instancia=instancia,
                modelo_alocacao="modelo",
                cursos=["CC", "ADM"],
                pasta_candidatos=Path(temp_dir) / "candidatos",
                tempo_subproblema=10,
                preparar_modelo=preparar_fake,
                resolver=resolver_fake,
                objetivo_incumbente_inicial=200.0,
            )

            self.assertEqual(incumbente["objetivo"], 180.0)
            self.assertEqual(len(historico), 2)
            self.assertTrue(historico[0]["melhorou"])
            self.assertEqual(historico[0]["curso"], "CC")
            self.assertEqual(historico[0]["tempo_solver_s"], 7.35)
            self.assertFalse(historico[1]["melhorou"])
            self.assertEqual(historico[1]["curso"], "ADM")
            self.assertFalse((Path(temp_dir) / "candidatos").exists())
            self.assertEqual(chamadas, [("CC", None), ("ADM", None)])
            self.assertEqual(
                preparacoes[0]["solucao_incumbente_x"],
                {("D1", "101-A", "Horario_2_1"): 0},
            )
            self.assertEqual(
                preparacoes[1]["solucao_incumbente_x"],
                {("D1", "101-A", "Horario_2_1"): 1},
            )

    def test_executar_passada_por_cursos_respeita_ordem_e_loga_posicao(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
            "D2": DisciplinaFake("CC", 3, 25, ["Horario_2_1"]),
            "D3": DisciplinaFake("ADM", 1, 80, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object(), "ADM": object()}
        chamadas = []

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            curso = ["CC", "ADM"][len(chamadas)]
            chamadas.append(curso)
            return {
                "status_nome": "OPTIMAL",
                "solucoes": 1,
                "objetivo": 200.0,
                "arquivo_solucao": arquivo_solucao,
                "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
            }

        _, historico = executar_passada_por_cursos(
            solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 1},
            instancia=instancia,
            modelo_alocacao="modelo",
            tempo_subproblema=10,
            objetivo_incumbente_inicial=200.0,
            preparar_modelo=lambda modelo, **kwargs: None,
            resolver=resolver_fake,
            ordem_cursos="maior-demanda",
            seed_ordem_cursos=42,
        )

        self.assertEqual(chamadas, ["CC", "ADM"])
        self.assertEqual([registro["curso"] for registro in historico], ["CC", "ADM"])
        self.assertEqual([registro["posicao_ordem_curso"] for registro in historico], [1, 2])
        self.assertTrue(
            all(registro["ordem_cursos"] == "maior-demanda" for registro in historico)
        )
        self.assertTrue(
            all(registro["seed_ordem_cursos"] == 42 for registro in historico)
        )

    def test_executar_passada_por_cursos_pode_salvar_candidatos_para_debug(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)

        with tempfile.TemporaryDirectory() as temp_dir:
            pasta_candidatos = Path(temp_dir) / "candidatos"

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text("# Objective value = 180.0\n", encoding="utf-8")
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": 180.0,
                    "arquivo_solucao": arquivo_solucao,
                    "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                    "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
                }

            executar_passada_por_cursos(
                solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 1},
                instancia=instancia,
                modelo_alocacao="modelo",
                cursos=["CC"],
                pasta_candidatos=pasta_candidatos,
                tempo_subproblema=10,
                objetivo_incumbente_inicial=200.0,
                preparar_modelo=lambda modelo, **kwargs: None,
                resolver=resolver_fake,
                salvar_candidatos=True,
            )

            self.assertTrue((pasta_candidatos / "candidato_curso_CC.sol").exists())

    def test_executar_passada_por_dia_turno_usa_executor_generico(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                30,
                {
                    "Horario_2_1": Horario(2, 1),
                    "Horario_4_13": Horario(4, 13),
                },
            ),
            "D2": DisciplinaFake(
                "ADM",
                1,
                30,
                {"Horario_2_8": Horario(2, 8)},
            ),
        }
        instancia = InstanciaFake(disciplinas)
        chamadas = []

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            chamadas.append(arquivo_solucao)
            return {
                "status_nome": "OPTIMAL",
                "solucoes": 1,
                "objetivo": 200.0,
                "arquivo_solucao": arquivo_solucao,
                "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
            }

        _, historico = executar_passada_por_dia_turno(
            solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 1},
            instancia=instancia,
            modelo_alocacao="modelo",
            tempo_subproblema=10,
            objetivo_incumbente_inicial=200.0,
            preparar_modelo=lambda modelo, **kwargs: None,
            resolver=resolver_fake,
        )

        self.assertEqual(
            [(registro["dia"], registro["turno"]) for registro in historico],
            [(2, "M"), (2, "T"), (4, "N")],
        )
        self.assertEqual(
            [registro["recurso"] for registro in historico],
            ["2_M", "2_T", "4_N"],
        )
        self.assertEqual(chamadas, [None, None, None])

    def test_executar_passada_por_cursos_exige_solucao_x_para_aceitar_melhoria(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            return {
                "status_nome": "OPTIMAL",
                "solucoes": 1,
                "objetivo": 180.0,
                "arquivo_solucao": arquivo_solucao,
                "solucao_x": None,
                "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
            }

        with self.assertRaisesRegex(ValueError, "solucao_x em memoria"):
            executar_passada_por_cursos(
                solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 1},
                instancia=instancia,
                modelo_alocacao="modelo",
                cursos=["CC"],
                tempo_subproblema=10,
                objetivo_incumbente_inicial=200.0,
                preparar_modelo=lambda modelo, **kwargs: None,
                resolver=resolver_fake,
            )

    def test_executar_passada_por_cursos_limita_subproblema_ao_tempo_restante(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        parametros_usados = []

        with tempfile.TemporaryDirectory() as temp_dir:
            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                parametros_usados.append(parametros_gurobi)
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text("# Objective value = 200.0\n", encoding="utf-8")
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": 200.0,
                    "arquivo_solucao": arquivo_solucao,
                    "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                    "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
                }

            _, historico = executar_passada_por_cursos(
                solucao_incumbente_x={("D1", "101-A", "Horario_2_1"): 1},
                instancia=instancia,
                modelo_alocacao="modelo",
                cursos=["CC"],
                pasta_candidatos=Path(temp_dir) / "candidatos",
                tempo_subproblema=300,
                objetivo_incumbente_inicial=200.0,
                tempo_fim_total=time.time() + 10,
                preparar_modelo=lambda modelo, **kwargs: None,
                resolver=resolver_fake,
            )

        self.assertLess(parametros_usados[0]["TimeLimit"], 300)
        self.assertLessEqual(parametros_usados[0]["TimeLimit"], 10)
        self.assertLess(historico[0]["tempo_limite_subproblema_s"], 300)

    def test_executar_fix_and_optimize_cursos_loop_completo(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object()}

        with tempfile.TemporaryDirectory() as temp_dir:
            melhor_sol = Path(temp_dir) / "melhor.sol"
            log_csv = Path(temp_dir) / "log.csv"
            log_json = Path(temp_dir) / "log.json"
            chamadas_resolver = []
            chamadas_construir = []
            chamadas_preparar = []
            chamadas_liberar = []

            def carregar_fake(*args):
                return instancia

            def construir_fake(inst, **kwargs):
                chamadas_construir.append((inst, kwargs))
                return "modelo"

            def preparar_fake(modelo, **kwargs):
                chamadas_preparar.append((modelo, kwargs))

            def liberar_fake(modelo):
                chamadas_liberar.append(modelo)
                return 0

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                chamadas_resolver.append(arquivo_solucao)
                objetivo = 300.0 if len(chamadas_resolver) == 1 else 250.0
                if arquivo_solucao:
                    Path(arquivo_solucao).write_text(
                        f"# Objective value = {objetivo}\n",
                        encoding="utf-8",
                    )
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": objetivo,
                    "arquivo_solucao": arquivo_solucao,
                    "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                    "lns": {"variaveis_x_livres": 10, "variaveis_x_fixadas": 90},
                }

            resultado = executar_fix_and_optimize_cursos(
                arquivo_melhor_solucao=str(melhor_sol),
                arquivo_log_csv=str(log_csv),
                arquivo_log_json=str(log_json),
                tempo_subproblema=5,
                carregar=carregar_fake,
                construir=construir_fake,
                preparar_modelo=preparar_fake,
                liberar_modelo=liberar_fake,
                resolver=resolver_fake,
            )

            self.assertEqual(resultado["etapa"], "fix_and_optimize_cursos")
            self.assertEqual(resultado["status"], "CONCLUIDO")
            self.assertEqual(resultado["objetivo_inicial"], 300.0)
            self.assertEqual(resultado["objetivo_final"], 250.0)
            self.assertEqual(resultado["ganho_absoluto"], 50.0)
            self.assertEqual(resultado["passadas_executadas"], 2)
            self.assertEqual(resultado["melhorias_aceitas"], 1)
            self.assertTrue(melhor_sol.exists())
            self.assertIn("# Objective value = 250.0", melhor_sol.read_text(encoding="utf-8"))
            self.assertTrue(log_csv.exists())
            self.assertTrue(log_json.exists())
            self.assertEqual(chamadas_resolver, [None, None, None])
            self.assertEqual(len(chamadas_construir), 1)
            self.assertEqual([chamada[0] for chamada in chamadas_preparar], ["modelo", "modelo"])
            self.assertEqual(chamadas_liberar, ["modelo"])

    def test_executar_fix_and_optimize_hibrido_alterna_ao_estagnar(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                30,
                {"Horario_2_1": Horario(2, 1)},
            ),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object()}
        objetivos = iter([300.0, 300.0, 250.0, 250.0, 250.0])

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            objetivo = next(objetivos)
            return {
                "status_nome": "OPTIMAL",
                "solucoes": 1,
                "objetivo": objetivo,
                "arquivo_solucao": arquivo_solucao,
                "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                "lns": {"variaveis_x_livres": 5, "variaveis_x_fixadas": 95},
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            resultado = executar_fix_and_optimize(
                tipo_vizinhanca="hibrida",
                arquivo_melhor_solucao=str(Path(temp_dir) / "melhor.sol"),
                arquivo_log_csv="",
                arquivo_log_json="",
                carregar=lambda *args: instancia,
                construir=lambda inst, **kwargs: "modelo",
                preparar_modelo=lambda modelo, **kwargs: None,
                liberar_modelo=lambda modelo: None,
                resolver=resolver_fake,
            )

        self.assertEqual(
            [registro["vizinhanca"] for registro in resultado["historico"]],
            ["curso", "dia_turno", "curso", "dia_turno"],
        )
        self.assertEqual(
            [registro["ciclo"] for registro in resultado["historico"]],
            [1, 1, 2, 2],
        )
        self.assertEqual(resultado["objetivo_final"], 250.0)
        self.assertEqual(resultado["melhorias_aceitas"], 1)
        self.assertEqual(resultado["passadas_executadas"], 4)
        self.assertEqual(resultado["tipo_vizinhanca"], "hibrida")

    def test_executar_fix_and_optimize_pode_usar_somente_dia_turno(self):
        disciplinas = {
            "D1": DisciplinaFake(
                "CC",
                1,
                30,
                {"Horario_2_1": Horario(2, 1)},
            ),
        }
        instancia = InstanciaFake(disciplinas)
        objetivos = iter([300.0, 290.0, 290.0])

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            objetivo = next(objetivos)
            return {
                "status_nome": "OPTIMAL",
                "solucoes": 1,
                "objetivo": objetivo,
                "arquivo_solucao": arquivo_solucao,
                "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                "lns": None,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            resultado = executar_fix_and_optimize(
                tipo_vizinhanca="dia_turno",
                arquivo_melhor_solucao=str(Path(temp_dir) / "melhor.sol"),
                arquivo_log_csv="",
                arquivo_log_json="",
                carregar=lambda *args: instancia,
                construir=lambda inst, **kwargs: "modelo",
                preparar_modelo=lambda modelo, **kwargs: None,
                liberar_modelo=lambda modelo: None,
                resolver=resolver_fake,
            )

        self.assertEqual(resultado["etapa"], "fix_and_optimize_dia_turno")
        self.assertEqual(resultado["objetivo_final"], 290.0)
        self.assertTrue(
            all(
                registro["vizinhanca"] == "dia_turno"
                for registro in resultado["historico"]
            )
        )

    def test_dia_turno_curso_executa_unioes_e_atualiza_incumbente(self):
        instancia = InstanciaFake({
            "C1": DisciplinaFake("CC", 1, 30, {"a": Horario(2, 1)}),
            "C2": DisciplinaFake("CC", 1, 30, {"a": Horario(3, 8)}),
            "A1": DisciplinaFake("ADM", 1, 30, {
                "a": Horario(2, 1), "b": Horario(4, 13),
            }),
        })
        objetivos = iter([100, 90, 95, 80, 80])
        preparacoes = []

        def resolver_fake(modelo, **kwargs):
            objetivo = next(objetivos)
            return {"solucoes": 1, "objetivo": objetivo,
                    "solucao_x": {("C1", "S1", "a"): objetivo},
                    "status_nome": "OPTIMAL"}

        with tempfile.TemporaryDirectory() as temp_dir:
            resultado = executar_fix_and_optimize(
                tipo_vizinhanca="dia_turno_curso",
                apenas_uma_passada=True,
                tempo_modelo_inicial=180,
                tempo_heuristica_inicial=180,
                tempo_subproblema=600,
                tempo_total_maximo=14400,
                ordem_cursos="aleatoria",
                seed_ordem_cursos=42,
                arquivo_melhor_solucao=str(Path(temp_dir) / "melhor.sol"),
                arquivo_log_csv=str(Path(temp_dir) / "historico.csv"),
                arquivo_log_json=str(Path(temp_dir) / "historico.json"),
                carregar=lambda *args: instancia,
                construir=lambda inst: "modelo",
                preparar_modelo=lambda modelo, **kwargs: preparacoes.append(kwargs),
                liberar_modelo=lambda modelo: None,
                resolver=resolver_fake,
            )
            self.assertIn("dia,turno,curso", (Path(temp_dir) / "historico.csv").read_text())
            dados = json.loads((Path(temp_dir) / "historico.json").read_text())
            parametros = dados["parametros"]
            self.assertEqual(dados["historico"], resultado["historico"])
            self.assertEqual(parametros, resultado["parametros"])
            self.assertEqual(parametros["tempo_modelo_inicial_s"], 180)
            self.assertEqual(parametros["tempo_heuristica_inicial_s"], 180)
            self.assertEqual(parametros["tempo_subproblema_s"], 600)
            self.assertEqual(parametros["tempo_total_maximo_s"], 14400)
            self.assertEqual(parametros["gurobi_inicial_NoRelHeurTime"], 180)
            self.assertEqual(parametros["gurobi_subproblema_NoRelHeurTime"], 0)
            self.assertEqual(parametros["ordem_cursos"], "alfabetica")
            self.assertIsNone(parametros["seed_ordem_cursos"])
            self.assertEqual(parametros["seed_ordem_cursos_solicitada"], 42)
            with (Path(temp_dir) / "historico.csv").open() as arquivo:
                linhas = list(csv.DictReader(arquivo))
            self.assertEqual(len(linhas), 4)
            for linha in linhas:
                self.assertEqual(linha["parametro_tempo_total_maximo_s"], "14400")
                self.assertEqual(linha["parametro_tipo_vizinhanca"], "dia_turno_curso")
                self.assertEqual(linha["tipo_registro"], "iteracao")
        self.assertEqual(resultado["objetivo_final"], 80)
        self.assertEqual(resultado["melhorias_aceitas"], 2)
        self.assertEqual([p["disciplinas_livres"] for p in preparacoes], [
            {"A1", "C1"}, {"A1", "C1", "C2"}, {"C1", "C2"}, {"A1"},
        ])
        self.assertEqual([p["solucao_incumbente_x"][("C1", "S1", "a")]
                          for p in preparacoes], [100, 90, 90, 80])
        self.assertEqual([(r["dia"], r["turno"], r["curso"])
                          for r in resultado["historico"]], [
            (2, "M", "ADM"), (2, "M", "CC"), (3, "T", "CC"), (4, "N", "ADM"),
        ])

    def test_executar_fix_and_optimize_rejeita_tipo_desconhecido(self):
        with self.assertRaisesRegex(ValueError, "Tipo de vizinhanca invalido"):
            executar_fix_and_optimize(tipo_vizinhanca="desconhecida")

    def test_executar_fix_and_optimize_cursos_retorna_sem_solucao_inicial(self):
        instancia = InstanciaFake({})

        with tempfile.TemporaryDirectory() as temp_dir:
            melhor_sol = Path(temp_dir) / "melhor.sol"
            chamadas_liberar = []

            def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
                return {
                    "status_nome": "TIME_LIMIT",
                    "solucoes": 0,
                    "objetivo": None,
                    "arquivo_solucao": None,
                    "solucao_x": None,
                    "lns": None,
                }

            resultado = executar_fix_and_optimize_cursos(
                arquivo_melhor_solucao=str(melhor_sol),
                arquivo_log_csv=str(Path(temp_dir) / "sem_solucao.csv"),
                arquivo_log_json=str(Path(temp_dir) / "sem_solucao.json"),
                carregar=lambda *args: instancia,
                construir=lambda inst, **kwargs: "modelo",
                liberar_modelo=lambda modelo: chamadas_liberar.append(modelo),
                resolver=resolver_fake,
            )

            self.assertEqual(resultado["status"], "SEM_SOLUCAO_INICIAL")
            dados = json.loads((Path(temp_dir) / "sem_solucao.json").read_text())
            self.assertEqual(dados["historico"], [])
            self.assertIsNone(dados["parametros"]["tempo_total_maximo_s"])
            with (Path(temp_dir) / "sem_solucao.csv").open() as arquivo:
                linhas = list(csv.DictReader(arquivo))
            self.assertEqual(len(linhas), 1)
            self.assertEqual(linhas[0]["tipo_registro"], "parametros")
            self.assertEqual(linhas[0]["parametro_tipo_vizinhanca"], "curso")
            self.assertEqual(resultado["passadas_executadas"], 0)
            self.assertEqual(resultado["total_iteracoes"], 0)
            self.assertFalse(melhor_sol.exists())
            self.assertEqual(chamadas_liberar, ["modelo"])

    def test_executar_fix_and_optimize_cursos_libera_modelo_apos_excecao(self):
        disciplinas = {
            "D1": DisciplinaFake("CC", 1, 30, ["Horario_2_1"]),
        }
        instancia = InstanciaFake(disciplinas)
        instancia.cursos = {"CC": object()}
        chamadas_liberar = []
        chamadas_resolver = []

        def resolver_fake(modelo, parametros_gurobi=None, arquivo_solucao=None):
            chamadas_resolver.append(arquivo_solucao)
            if len(chamadas_resolver) == 1:
                return {
                    "status_nome": "OPTIMAL",
                    "solucoes": 1,
                    "objetivo": 300.0,
                    "arquivo_solucao": None,
                    "solucao_x": {("D1", "101-A", "Horario_2_1"): 1},
                    "lns": None,
                }
            raise RuntimeError("falha no subproblema")

        with self.assertRaisesRegex(RuntimeError, "falha no subproblema"):
            executar_fix_and_optimize_cursos(
                arquivo_log_csv="",
                arquivo_log_json="",
                carregar=lambda *args: instancia,
                construir=lambda inst, **kwargs: "modelo",
                preparar_modelo=lambda modelo, **kwargs: None,
                liberar_modelo=lambda modelo: chamadas_liberar.append(modelo),
                resolver=resolver_fake,
            )

        self.assertEqual(chamadas_liberar, ["modelo"])


if __name__ == "__main__":
    unittest.main()
