import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import pandas as pd

from alocador_salas.data.extrai_horarios_aula import ExtraiHorariosAula


class TestNovosSemestres(unittest.TestCase):
    def linha(self, cod='D1', turma=7, horario='2M1', inicio='01/03', fim='31/03'):
        return dict(cod=cod, num_turma=turma, ch_ccr=60, curso='ENGENHARIA CIVIL',
                    fase=1, horario=f'{horario} ({inicio}/2026 - {fim}/2026)',
                    vagas=30, nome_ccr=cod)

    def ler(self, linhas):
        with patch('pandas.read_excel', return_value=pd.DataFrame(linhas)), patch.object(
            ExtraiHorariosAula, 'cria_salas_preferenciais', return_value={}
        ), redirect_stdout(StringIO()):
            return ExtraiHorariosAula('', '').extrai_horarios_aula()

    def test_usa_turma_real_e_cobre_novos_cursos_e_medicina(self):
        disciplinas, _, fases, cursos = self.ler([self.linha(turma=7.0)])
        self.assertEqual(list(disciplinas), ['D1_7'])
        self.assertEqual(disciplinas['D1_7'].curso, 'ECV')
        self.assertIn('ECV', cursos)
        for fase in (11, 12):
            self.assertEqual(fases[f'MED_{fase}'].curso, 'MED')

    def test_sem_coluna_preserva_contador(self):
        linha = self.linha()
        del linha['num_turma']
        disciplinas, *_ = self.ler([linha, linha])
        self.assertEqual(set(disciplinas), {'D1_1', 'D1_2'})

    def test_rejeita_turma_invalida(self):
        for valor in (None, '', 'abc', 0, -1, 1.5, float('inf')):
            with self.subTest(valor=valor), self.assertRaisesRegex(ValueError, 'num_turma invalido'):
                self.ler([self.linha(turma=valor)])

    def test_rejeita_duplicata_mesmo_apos_agrupar(self):
        a = self.linha('D1', inicio='01/03', fim='31/03')
        b = self.linha('D2', inicio='01/04', fim='30/04')
        with self.assertRaisesRegex(ValueError, 'D2_7.*duas vezes'):
            self.ler([a, b, b])

    def test_trocas_de_representante_preservam_todos_os_membros(self):
        disciplinas, *_ = self.ler([
            self.linha('D1'),
            self.linha('D2', inicio='01/04', fim='30/04'),
            self.linha('D3', horario='2M12', inicio='01/05', fim='31/05'),
            self.linha('D4', horario='2M123', inicio='01/06', fim='30/06'),
        ])
        self.assertEqual(list(disciplinas), ['D4_7'])
        self.assertEqual({d.cod for d in disciplinas['D4_7'].agrupamento}, {'D1_7', 'D2_7', 'D3_7'})
        self.assertTrue(all(not d.agrupamento for d in disciplinas['D4_7'].agrupamento))

    def test_nao_agrupa_quando_sobrepoe_um_filho(self):
        disciplinas, *_ = self.ler([
            self.linha('D1'),
            self.linha('D2', inicio='01/04', fim='30/04'),
            self.linha('D3', inicio='15/04', fim='25/04'),
        ])
        self.assertEqual(len(disciplinas), 2)
