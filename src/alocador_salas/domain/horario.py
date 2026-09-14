from typing import Literal, TypeAlias


Turno: TypeAlias = Literal["M", "T", "N"]
DiaTurno: TypeAlias = tuple[int, Turno]

DIAS_VALIDOS = frozenset(range(2, 8))
TURNOS_VALIDOS: tuple[Turno, ...] = ("M", "T", "N")


def turno_da_faixa(faixa: int) -> Turno:
    """Converte uma faixa semanal no turno canonico usado pela LNS."""
    if not 1 <= faixa <= 18:
        raise ValueError(f"Faixa de horario invalida: {faixa}. Esperado valor entre 1 e 18.")
    if faixa <= 6:
        return "M"
    if faixa <= 12:
        return "T"
    return "N"


def dia_turno(dia: int, faixa: int) -> DiaTurno:
    """Retorna a chave canonica (dia, turno) correspondente ao horario."""
    if dia not in DIAS_VALIDOS:
        raise ValueError(f"Dia de horario invalido: {dia}. Esperado valor entre 2 e 7.")
    return dia, turno_da_faixa(faixa)


class Horario:
    def __init__(self,dia,faixa):
        self.dia = dia
        self.faixa = faixa

    def converte_horario(self):
        # Conversão de horário do padrão do sigaa para a o padrão utilizado na tabela de saída.
        dia=dict()
        dia[2]="SEG"
        dia[3]="TER"
        dia[4]="QUA"
        dia[5]="QUI"
        dia[6]="SEX"
        dia[7]="SAB"
        return str(dia[self.dia]+"-"+self.get_periodo())
    
    def get_faixa_convertida(self):
        if self.faixa <= 6:
            return self.faixa
        elif self.faixa>6 and self.faixa<=12:
            return self.faixa - 6
        else:
            return self.faixa - 12
    
    def get_periodo(self):
        if self.faixa <= 6:
            return "M"
        elif self.faixa>6 and self.faixa<=12:
            return "V"
        else:
            return "N"
    
