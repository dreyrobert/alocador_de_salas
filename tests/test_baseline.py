import csv
import os
import sys
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from alocador_salas.domain.disciplina import Disciplina
from alocador_salas.domain.horario import Horario
from alocador_salas.validation.verifica_solucao import VerificaSolucao

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.simplefilter("ignore", DeprecationWarning)

try:
    import pandas  # noqa: F401
except ModuleNotFoundError:
    TEM_PANDAS = False
else:
    TEM_PANDAS = True


class ValorSolucao:
    def __init__(self, valor):
        self.X = valor


class ModeloGurobiFake:
    def __init__(self):
        self.SolCount = 1
        self.status = 2
        self.ObjVal = 10.0
        self.ObjBound = 10.0
        self.MIPGap = 0.0
        self.Runtime = 0.5
        self.parametros = {}
        self.otimizou = False
        self.arquivo_escrito = None
        self.atualizacoes = 0

    def setParam(self, parametro, valor):
        self.parametros[parametro] = valor

    def optimize(self):
        self.otimizou = True

    def write(self, arquivo_solucao):
        self.arquivo_escrito = arquivo_solucao

    def update(self):
        self.atualizacoes += 1


def cria_disciplina(codigo, horarios, curso="CIÊNCIA DA COMPUTAÇÃO", fase="1", alunos=20):
    return Disciplina(
        curso,
        codigo,
        60,
        alunos,
        horarios,
        "",
        {},
        ["101-A"],
        [fase],
        codigo,
        0,
    )


class TestHorario(unittest.TestCase):
    def test_converte_horario_para_dia_e_periodo_da_tabela(self):
        self.assertEqual(Horario(2, 1).converte_horario(), "SEG-M")
        self.assertEqual(Horario(4, 8).converte_horario(), "QUA-V")
        self.assertEqual(Horario(6, 14).converte_horario(), "SEX-N")

    def test_converte_faixa_para_periodo_local(self):
        self.assertEqual(Horario(2, 6).get_faixa_convertida(), 6)
        self.assertEqual(Horario(2, 7).get_faixa_convertida(), 1)
        self.assertEqual(Horario(2, 13).get_faixa_convertida(), 1)


class TestDisciplina(unittest.TestCase):
    def test_abrevia_curso_e_formata_disciplina_regular(self):
        disciplina = Disciplina(
            curso="CIÊNCIA DA COMPUTAÇÃO",
            nome_ccr="Algoritmos",
            ch_ccr=60,
            alunos=35,
            horarios={},
            horarioString="2M12",
            periodoDuracao={},
            salasPreferenciais=["101-A"],
            fase=["3"],
            cod="GEX001_1",
            fusao=0,
        )

        self.assertEqual(disciplina.curso, "CC")
        self.assertEqual(disciplina.formata_individual(), "CC - 3 (GEX001_1)")

    def test_agrupamento_usa_maior_demanda_e_uniao_de_horarios(self):
        principal = Disciplina(
            "MATEMÁTICA",
            "Calculo A",
            60,
            20,
            {"Horario_2_1": Horario(2, 1)},
            "2M1",
            {},
            [],
            ["1"],
            "MAT001_1",
            0,
        )
        agrupada = Disciplina(
            "MATEMÁTICA",
            "Calculo B",
            60,
            45,
            {"Horario_2_2": Horario(2, 2)},
            "2M2",
            {},
            [],
            ["1"],
            "MAT002_1",
            0,
        )

        principal.agrupamento.append(agrupada)

        self.assertEqual(principal.max_alunos_agrupamento(), 45)
        self.assertEqual(
            set(principal.horarios_agrupamento()),
            {"Horario_2_1", "Horario_2_2"},
        )


class TestDadosBasicos(unittest.TestCase):
    @unittest.skipUnless(TEM_PANDAS, "pandas nao esta instalado")
    def test_extrai_salas_do_csv_por_bloco_com_capacidade(self):
        from alocador_salas.data.extrai_salas import ExtraiSalas

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo = Path(temp_dir) / "salas.csv"
            with arquivo.open("w", newline="", encoding="UTF-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["SALAS", "CADEIRAS"])
                writer.writeheader()
                writer.writerow({"SALAS": "BLOCO A", "CADEIRAS": ""})
                writer.writerow({"SALAS": "101 Sala", "CADEIRAS": "40"})
                writer.writerow({"SALAS": "102 Sala", "CADEIRAS": "25"})
                writer.writerow({"SALAS": "BLOCO B", "CADEIRAS": ""})
                writer.writerow({"SALAS": "201 Sala", "CADEIRAS": "55"})

            salas = ExtraiSalas(str(arquivo)).extrai_salas()

        self.assertEqual(list(salas), ["101-A", "102-A", "201-B"])
        self.assertEqual(salas["101-A"].capacidade, 40)
        self.assertEqual(salas["201-B"].capacidade, 55)

    @unittest.skipUnless(TEM_PANDAS, "pandas nao esta instalado")
    def test_matriz_distancia_e_quadrada_simetrica_e_com_diagonal_zero(self):
        from alocador_salas.data.gera_matriz_distancia import GeraMatrizDistancia

        salas = {
            "101-A": object(),
            "103-A": object(),
            "201-B": object(),
        }

        matriz = GeraMatrizDistancia(salas).gera_matriz()

        self.assertEqual(len(matriz), 3)
        self.assertEqual([linha[i] for i, linha in enumerate(matriz)], [0, 0, 0])
        self.assertEqual(matriz[0][1], 2)
        self.assertEqual(matriz[0][2], matriz[2][0])


@unittest.skipUnless(TEM_PANDAS, "pandas nao esta instalado")
class TestExtraiHorariosAula(unittest.TestCase):
    def escreve_planilhas(self, pasta):
        import pandas as pd

        arquivo_horarios = Path(pasta) / "horarios.xlsx"
        arquivo_preferenciais = Path(pasta) / "preferenciais.xlsx"
        pd.DataFrame(
            [
                {
                    "cod": "GEX001",
                    "ch_ccr": 60,
                    "curso": "CIÊNCIA DA COMPUTAÇÃO",
                    "fase": "3",
                    "horario": "2M12 (01/03/2024 - 30/06/2024)",
                    "vagas": 35,
                    "nome_ccr": "Algoritmos",
                },
                {
                    "cod": "GEX002",
                    "ch_ccr": 30,
                    "curso": "CIÊNCIA DA COMPUTAÇÃO;MATEMÁTICA",
                    "fase": "3;1",
                    "horario": "4T34 (01/03/2024 - 30/06/2024)",
                    "vagas": 25,
                    "nome_ccr": "Topicos compartilhados",
                },
            ]
        ).to_excel(arquivo_horarios, index=False)
        pd.DataFrame(
            [
                ["CIÊNCIA DA COMPUTAÇÃO", "101-A, 102-A"],
                ["GEX001", "103-A"],
            ]
        ).to_excel(arquivo_preferenciais, index=False, header=False)
        return arquivo_horarios, arquivo_preferenciais

    def test_extrai_disciplinas_horarios_fases_cursos_e_preferencias(self):
        from alocador_salas.data.extrai_horarios_aula import ExtraiHorariosAula

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo_horarios, arquivo_preferenciais = self.escreve_planilhas(temp_dir)
            with redirect_stdout(StringIO()):
                disciplinas, horarios, fases, cursos = ExtraiHorariosAula(
                    str(arquivo_horarios),
                    str(arquivo_preferenciais),
                ).extrai_horarios_aula()

        self.assertIn("GEX001_1", disciplinas)
        self.assertIn("GEX002_1", disciplinas)
        self.assertEqual(disciplinas["GEX001_1"].curso, "CC")
        self.assertEqual(disciplinas["GEX001_1"].salasPreferenciais, ["103-A"])
        self.assertEqual(
            set(disciplinas["GEX001_1"].horarios),
            {"Horario_2_1", "Horario_2_2"},
        )
        self.assertEqual(disciplinas["GEX002_1"].fusao, 1)
        self.assertEqual(horarios["Horario_4_9"].converte_horario(), "QUA-V")
        self.assertEqual(fases["CC_3"].curso, "CC")
        self.assertIn("CC", cursos)

    def test_identifica_sobreposicao_de_horario_e_periodo(self):
        from alocador_salas.data.extrai_horarios_aula import ExtraiHorariosAula

        extrator = ExtraiHorariosAula("", "")

        self.assertTrue(extrator.verifica_sobreposicao_horario_aula("25M12", "2M2"))
        self.assertFalse(extrator.verifica_sobreposicao_horario_aula("25M12", "2T2"))
        self.assertTrue(
            extrator.verfica_sobreposicao(
                "(01/03/2024 - 30/06/2024)",
                "(15/04/2024 - 15/07/2024)",
            )
        )
        self.assertFalse(
            extrator.verfica_sobreposicao(
                "(01/03/2024 - 30/03/2024)",
                "(01/04/2024 - 30/04/2024)",
            )
        )


class TestVerificaSolucao(unittest.TestCase):
    def test_detecta_conflito_quando_disciplinas_ocupam_mesma_sala_e_faixa(self):
        horarios = {
            "Horario_2_1": Horario(2, 1),
            "Horario_2_2": Horario(2, 2),
            "Horario_2_3": Horario(2, 3),
        }
        disciplinas = {
            "D1": cria_disciplina("D1", {"Horario_2_1": horarios["Horario_2_1"], "Horario_2_2": horarios["Horario_2_2"]}),
            "D2": cria_disciplina("D2", {"Horario_2_2": horarios["Horario_2_2"], "Horario_2_3": horarios["Horario_2_3"]}),
        }
        salas = {"101-A": object()}
        x = {}
        for disciplina in disciplinas:
            for sala in salas:
                for horario in disciplinas[disciplina].horarios_agrupamento():
                    x[disciplina, sala, horario] = ValorSolucao(1)

        with redirect_stdout(StringIO()):
            conflitos = VerificaSolucao(disciplinas, salas, horarios, x).verifica_conflito_turno()

        self.assertEqual(len(conflitos), 1)
        self.assertEqual(conflitos[0][0], "101-A-SEG-M")

    def test_nao_detecta_conflito_em_faixas_distintas_da_mesma_sala_turno(self):
        horarios = {
            "Horario_2_1": Horario(2, 1),
            "Horario_2_3": Horario(2, 3),
        }
        disciplinas = {
            "D1": cria_disciplina("D1", {"Horario_2_1": horarios["Horario_2_1"]}),
            "D2": cria_disciplina("D2", {"Horario_2_3": horarios["Horario_2_3"]}),
        }
        salas = {"101-A": object()}
        x = {
            ("D1", "101-A", "Horario_2_1"): ValorSolucao(1),
            ("D2", "101-A", "Horario_2_3"): ValorSolucao(1),
        }

        with redirect_stdout(StringIO()):
            conflitos = VerificaSolucao(disciplinas, salas, horarios, x).verifica_conflito_turno()

        self.assertEqual(conflitos, [])


class TestResolverModelo(unittest.TestCase):
    def test_preparar_modelo_para_vizinhanca_atualiza_fixacoes_no_modelo_existente(self):
        from alocador_salas.optimization import solve

        modelo = ModeloGurobiFake()
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): ValorSolucao(1.0),
            ("D2", "101-A", "Horario_2_1"): ValorSolucao(0.0),
            ("D3", "101-A", "Horario_2_1"): ValorSolucao(1.0),
        }
        for variavel in x_vars.values():
            variavel.LB = 0
            variavel.UB = 1
            variavel.Start = None

        modelo_alocacao = type(
            "ModeloAlocacaoFake",
            (),
            {
                "modelo": modelo,
                "x": x_vars,
                "resumo_lns": None,
                "disciplinas_livres": set(),
                "chaves_x_fixadas": {("D2", "101-A", "Horario_2_1")},
            },
        )()
        x_vars[("D2", "101-A", "Horario_2_1")].LB = 0
        x_vars[("D2", "101-A", "Horario_2_1")].UB = 0
        solucao = {
            ("D1", "101-A", "Horario_2_1"): 1,
            ("D2", "101-A", "Horario_2_1"): 0,
            ("D3", "101-A", "Horario_2_1"): 1,
        }

        chaves_fixadas, resumo = solve.preparar_modelo_para_vizinhanca(
            modelo_alocacao,
            solucao_incumbente_x=solucao,
            disciplinas_livres={"D2"},
        )

        self.assertEqual(chaves_fixadas, {
            ("D1", "101-A", "Horario_2_1"),
            ("D3", "101-A", "Horario_2_1"),
        })
        self.assertEqual(x_vars[("D2", "101-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D2", "101-A", "Horario_2_1")].UB, 1)
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].LB, 1)
        self.assertEqual(x_vars[("D3", "101-A", "Horario_2_1")].UB, 1)
        self.assertEqual(modelo_alocacao.disciplinas_livres, {"D2"})
        self.assertEqual(modelo_alocacao.chaves_x_fixadas, chaves_fixadas)
        self.assertEqual(modelo_alocacao.resumo_lns, resumo)
        self.assertEqual(resumo["fixacoes_liberadas"], 1)
        self.assertEqual(modelo.atualizacoes, 1)

    def test_liberar_fixacoes_modelo_limpa_estado_de_modelo_reutilizado(self):
        from alocador_salas.optimization import solve

        modelo = ModeloGurobiFake()
        x_vars = {
            ("D1", "101-A", "Horario_2_1"): ValorSolucao(1.0),
            ("D2", "101-A", "Horario_2_1"): ValorSolucao(0.0),
        }
        for variavel in x_vars.values():
            variavel.LB = 0
            variavel.UB = 0

        modelo_alocacao = type(
            "ModeloAlocacaoFake",
            (),
            {
                "modelo": modelo,
                "x": x_vars,
                "disciplinas_livres": {"D1"},
                "chaves_x_fixadas": set(x_vars),
            },
        )()

        liberadas = solve.liberar_fixacoes_modelo(modelo_alocacao)

        self.assertEqual(liberadas, 2)
        self.assertEqual(modelo_alocacao.chaves_x_fixadas, set())
        self.assertEqual(modelo_alocacao.disciplinas_livres, set())
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].LB, 0)
        self.assertEqual(x_vars[("D1", "101-A", "Horario_2_1")].UB, 1)
        self.assertEqual(x_vars[("D2", "101-A", "Horario_2_1")].UB, 1)
        self.assertEqual(modelo.atualizacoes, 1)

    def test_retorna_solucao_x_em_memoria_quando_ha_solucao(self):
        from alocador_salas.optimization import solve

        class GRBFake:
            OPTIMAL = 2
            TIME_LIMIT = 9
            INFEASIBLE = 3
            INF_OR_UNBD = 4
            UNBOUNDED = 5
            SOLUTION_LIMIT = 10
            INTERRUPTED = 11

        modelo = ModeloGurobiFake()
        modelo_alocacao = type(
            "ModeloAlocacaoFake",
            (),
            {
                "modelo": modelo,
                "x": {
                    ("D1", "101-A", "Horario_2_1"): ValorSolucao(1.0),
                    ("D1", "102-A", "Horario_2_1"): ValorSolucao(0.0),
                },
                "restricoes_removidas": {"c1"},
                "resumo_lns": {"variaveis_x_total": 2},
                "disciplinas_livres": {"D1"},
            },
        )()

        with patch.object(solve, "gp", type("GpFake", (), {"GRB": GRBFake})):
            with redirect_stdout(StringIO()):
                resultado = solve.resolver_modelo(
                    modelo_alocacao,
                    parametros_gurobi={"TimeLimit": 5},
                    arquivo_solucao="saida.sol",
                )

        self.assertTrue(modelo.otimizou)
        self.assertEqual(modelo.parametros["TimeLimit"], 5)
        self.assertEqual(modelo.arquivo_escrito, "saida.sol")
        self.assertEqual(
            resultado["solucao_x"],
            {
                ("D1", "101-A", "Horario_2_1"): 1,
                ("D1", "102-A", "Horario_2_1"): 0,
            },
        )
        self.assertEqual(resultado["arquivo_solucao"], "saida.sol")


@unittest.skipUnless(TEM_PANDAS, "pandas nao esta instalado")
class TestGeraPlanilhaSaida(unittest.TestCase):
    def test_gera_tabela_de_alocacoes_com_aba_de_conflitos(self):
        import pandas as pd
        from alocador_salas.reports.gera_planilha_saida import GeraPlanilhaSaida

        horarios = {"Horario_2_1": Horario(2, 1)}
        disciplinas = {"D1": cria_disciplina("D1", horarios)}
        salas = {"101-A": object()}
        x = {("D1", "101-A", "Horario_2_1"): ValorSolucao(1)}

        with tempfile.TemporaryDirectory() as temp_dir:
            GeraPlanilhaSaida(
                disciplinas,
                salas,
                horarios,
                x,
                temp_dir + os.sep,
                "planilha.xlsx",
            ).cria_tabela_alocacoes([["101-A-SEG-M", ["D1-1", "D2-1"]]])

            arquivo = Path(temp_dir) / "tabela_alocacoes.xlsx"
            alocacoes = pd.read_excel(arquivo, sheet_name="Alocações")
            conflitos = pd.read_excel(arquivo, sheet_name="Conflitos")

        self.assertEqual(alocacoes.loc[0, "cod"], "D1")
        self.assertEqual(alocacoes.loc[0, "sala"], "['101-A']")
        self.assertEqual(conflitos.loc[0, "SALA-TURNO"], "101-A-SEG-M")

    def test_exporta_planilha_de_alocacoes_com_disciplina_alocada(self):
        import openpyxl
        from alocador_salas.reports.gera_planilha_saida import GeraPlanilhaSaida

        horarios = {"Horario_2_1": Horario(2, 1)}
        disciplinas = {"D1": cria_disciplina("D1", horarios)}
        salas = {"101-A": object()}
        x = {("D1", "101-A", "Horario_2_1"): ValorSolucao(1)}

        with tempfile.TemporaryDirectory() as temp_dir:
            arquivo = Path(temp_dir) / "planilha.xlsx"
            with redirect_stdout(StringIO()):
                GeraPlanilhaSaida(
                    disciplinas,
                    salas,
                    horarios,
                    x,
                    temp_dir + os.sep,
                    arquivo.name,
                ).exporta_alocacoes()

            workbook = openpyxl.load_workbook(arquivo)
            worksheet = workbook.active
            valores = [cell.value for row in worksheet.iter_rows() for cell in row]
            workbook.close()

        self.assertIn("CC - 1 (D1)", valores)


class TestWebApp(unittest.TestCase):
    def test_home_e_wait_renderizam_paginas(self):
        sys.path.insert(0, str(Path.cwd() / "web"))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                from web.app import app

                app.config["TESTING"] = True
                client = app.test_client()

                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/wait").status_code, 200)
        finally:
            sys.path.pop(0)

    def test_solve_salva_uploads_e_dispara_thread_de_processamento(self):
        sys.path.insert(0, str(Path.cwd() / "web"))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                from web.app import app

                app.config["TESTING"] = True
                client = app.test_client()

                thread_mock = MagicMock()
                saves = []

                def fake_save(file_storage, destino):
                    saves.append((file_storage.filename, destino))

                with patch("web.app.threading.Thread", return_value=thread_mock), patch(
                    "werkzeug.datastructures.FileStorage.save",
                    autospec=True,
                    side_effect=fake_save,
                ):
                    resposta = client.post(
                        "/solve",
                        data={
                            "email": "teste@example.com",
                            "salas_preferenciais": (BytesIO(b"pref"), "salas_preferenciais.xlsx"),
                            "salas": (BytesIO(b"SALAS,CADEIRAS\n"), "salas.csv"),
                            "horarios": (BytesIO(b"horarios"), "horarios.xlsx"),
                        },
                        content_type="multipart/form-data",
                    )

                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(thread_mock.start.called)
                self.assertEqual(
                    [destino for _, destino in saves],
                    [
                        "./web/static/dados/salas_preferenciais.xlsx",
                        "./web/static/dados/salas.csv",
                        "./web/static/dados/horarios.xlsx",
                    ],
                )
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
