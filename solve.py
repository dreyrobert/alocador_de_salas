from __future__ import annotations

from classes.Horario import Horario
from classes.Disciplina import Disciplina
from classes.Sala import Sala
from extrai_salas import ExtraiSalas
from extrai_horarios_aula import ExtraiHorariosAula
from gera_matriz_distancia import GeraMatrizDistancia
from gera_planilha_saida import GeraPlanilhaSaida
from verifica_solucao import VerificaSolucao
from lns_fix_and_optimize import (
    aplicar_start_e_fixacao_x,
    disciplinas_da_fase,
    disciplinas_do_curso,
    extrair_solucao_x,
    parse_solucao_x,
)
import argparse
from dataclasses import dataclass
import json
try:
    import gurobipy as gp
    from gurobipy import GRB
except ModuleNotFoundError:
    gp = None
    GRB = None



@dataclass
class InstanciaAlocacao:
    salas: dict
    salas_lista: list
    matriz_dist: list
    disciplinas: dict
    horarios: dict
    fases: dict
    cursos: dict


@dataclass
class ModeloAlocacao:
    modelo: gp.Model
    instancia: InstanciaAlocacao
    x: dict
    y: dict
    w: dict
    t: dict
    z: dict
    v: dict
    restricoes_removidas: set
    resumo_lns: dict | None
    disciplinas_livres: set


def carregar_instancia(
    arquivo_horarios,
    arquivo_salas,
    arquivo_salas_preferenciais,
):
    salas = ExtraiSalas(arquivo_salas).extrai_salas()
    salas_lista = list(salas.keys())
    matriz_dist = GeraMatrizDistancia(salas).gera_matriz()
    disciplinas, horarios, fases, cursos = ExtraiHorariosAula(
        arquivo_horarios,
        arquivo_salas_preferenciais,
    ).extrai_horarios_aula()

    return InstanciaAlocacao(
        salas=salas,
        salas_lista=salas_lista,
        matriz_dist=matriz_dist,
        disciplinas=disciplinas,
        horarios=horarios,
        fases=fases,
        cursos=cursos,
    )


def selecionar_disciplinas_livres(
    disciplinas,
    disciplinas_livres=None,
    fase_livre=None,
    curso_livre=None,
):
    selecionadas = set(disciplinas_livres or [])
    if fase_livre:
        curso, fase = fase_livre
        selecionadas.update(disciplinas_da_fase(disciplinas, curso, fase))
    if curso_livre:
        selecionadas.update(disciplinas_do_curso(disciplinas, curso_livre))
    return selecionadas


def aplicar_start_incumbente_x(x, solucao_incumbente_x, disciplinas_livres):
    if solucao_incumbente_x is None:
        return None

    if disciplinas_livres:
        return aplicar_start_e_fixacao_x(
            x,
            solucao_incumbente_x,
            disciplinas_livres,
        )

    resumo_lns = {
        "variaveis_x_total": len(x),
        "variaveis_x_livres": len(x),
        "variaveis_x_fixadas": 0,
        "valores_start_definidos": 0,
        "chaves_sem_valor_incumbente": 0,
    }
    for chave, variavel in x.items():
        valor = solucao_incumbente_x.get(chave)
        if valor is None:
            resumo_lns["chaves_sem_valor_incumbente"] += 1
            continue
        variavel.Start = valor
        resumo_lns["valores_start_definidos"] += 1

    return resumo_lns


def construir_modelo(
    instancia,
    restricoes_removidas=None,
    solucao_incumbente_x=None,
    disciplinas_livres=None,
    fase_livre=None,
    curso_livre=None,
):
    restricoes_removidas = set(restricoes_removidas or [])
    disciplinas_livres = selecionar_disciplinas_livres(
        instancia.disciplinas,
        disciplinas_livres=disciplinas_livres,
        fase_livre=fase_livre,
        curso_livre=curso_livre,
    )

    salas = instancia.salas
    salasLista = instancia.salas_lista
    matriz_dist = instancia.matriz_dist
    disciplinas = instancia.disciplinas
    horarios = instancia.horarios
    fases = instancia.fases
    cursos = instancia.cursos

    # Criando o modelo
    m = gp.Model()

    # Variaveis de ajuste de peso
    M1 = 250
    M2 = 150
    M3 = 2000
    M4 = 5
    M5 = 0.5

    # Variaveis
    x = {}
    for d in disciplinas:
        for h in disciplinas[d].horarios_agrupamento():
            for s in salas:
                x[d, s, h] = m.addVar(vtype=gp.GRB.BINARY, name=f"x[{d},{s},{h}]")

    resumo_lns = aplicar_start_incumbente_x(
        x,
        solucao_incumbente_x,
        disciplinas_livres,
    )

    y = m.addVars(disciplinas,salas,vtype=gp.GRB.INTEGER, name="y")
    w = m.addVars(salasLista,cursos,vtype=gp.GRB.BINARY,name="w")
    t = {}
    for si in salasLista:
        for sj in salasLista:
            if salasLista.index(si)<salasLista.index(sj):
                for c in cursos:
                    t[si,sj,c] = m.addVar(vtype=gp.GRB.BINARY,name=f"t[{si},{sj},{c}]")

    z = m.addVars(salasLista,fases,vtype=gp.GRB.BINARY,name="v")
    v = {}
    for si in salasLista:
        for sj in salasLista:
            if salasLista.index(si)<salasLista.index(sj):
                for f in fases:
                    v[si,sj,f] = m.addVar(vtype=gp.GRB.BINARY,name=f"v[{si},{sj},{f}]")

    # Cria vetor de variaveis das salas preferenciais
    vet_salas_preferenciais=[]

    for d in disciplinas:
        for h in disciplinas[d].horarios_agrupamento():
            for s in salas:
                if s not in disciplinas[d].salasPreferenciais:
                    vet_salas_preferenciais.append(x[d,s,h])
    
    # Cria vetor das alocacoes das salas
    vet_alocacoes=[]
    for d in disciplinas:
        for h in disciplinas[d].horarios_agrupamento():
            vet_alocacoes.append((1 - gp.quicksum(x[d,s,h] for s in salas)))

    # Funcao objetivo
    m.setObjective(gp.quicksum(y[d,s] for d in disciplinas for s in salas)*M1 +
                gp.quicksum(vet_salas_preferenciais)*M2 +
                gp.quicksum(vet_alocacoes)*M3 +
                gp.quicksum(matriz_dist[salasLista.index(si)][salasLista.index(sj)] * v[si,sj,f] for si in salas for sj in salas 
                     if salasLista.index(si) < salasLista.index(sj) for f in fases)*M4+
                gp.quicksum(z[s,f]for s in salas for f in fases)*M4+
                gp.quicksum(matriz_dist[salasLista.index(si)][salasLista.index(sj)] * t[si,sj,c] for si in salas for sj in salas 
                           if salasLista.index(si) < salasLista.index(sj) for c in cursos)*M5,
    sense=gp.GRB.MINIMIZE
    )

    ## == Restricoes

    # No máximo uma disciplina (turma) pode ser alocada a uma sala em um determinado horário:
    if "c1" not in restricoes_removidas:
        c1 = m.addConstrs(
            gp.quicksum(x[d, s, h] for d in disciplinas if h in disciplinas[d].horarios_agrupamento()) <= 1
            for s in salas for h in horarios
        )

    # No máximo uma sala pode ser alocada a uma disciplina em um determinado horário
    if "c2" not in restricoes_removidas:
        c2 = m.addConstrs(
            gp.quicksum(x[d,s,h] for s in salas ) <= 1 for d in disciplinas for h in disciplinas[d].horarios_agrupamento()
        )

    # TODO Melhorar o tratamento dos dados de uma disciplina considerando que
    # ela pode ser um agrupamento (ex.: uso dos metodos max_alunos_agrupamento
    # e horarios_agrupamento)
    # Uma sala não pode ser alocada a uma disciplina cujo número de alunos ultrapasse a sua capacidade:
    if "c3" not in restricoes_removidas:
        c3 = m.addConstrs(
            x[d,s,h] * disciplinas[d].max_alunos_agrupamento() <= salas[s].capacidade for d in disciplinas for s in salas for h in disciplinas[d].horarios_agrupamento())


    # Uma sala é alocada a uma disciplina se a sala é alocada à disciplina em algum horário:
    if "c4" not in restricoes_removidas:
        c4 = m.addConstrs(
            y[d,s] >= x[d,s,h] for d in disciplinas for s in salas for h in disciplinas[d].horarios_agrupamento())
    

    # Uma sala é aloacada a uma fase (e curso) se a sala é aloaca à uma disciplina dessa mesma fase em algum horário
    if "c5" not in restricoes_removidas:
        c5 = m.addConstrs(
            z[s,f] >= x[d,s,h] for d in disciplinas for s in salasLista for h in disciplinas[d].horarios_agrupamento() for f in fases if fases[f].fase == disciplinas[d].fase and fases[f].curso == disciplinas[d].curso
        )

    # Indica as duplas de salas aloacadas para uma mesma fase que serão usadas no somatório de distância de salas alocadas a determinada fase
    if "c6" not in restricoes_removidas:
        c6 = m.addConstrs(
            v[si,sj,f] >= (z[si,f]+z[sj,f] - 1) for si in salasLista for sj in salasLista if salasLista.index(si) < salasLista.index(sj) for f in fases
        )

    # Uma sala é alocada a um curso se a sala é alocada à uma disciplina desse mesmo curso em algum horário.
    if "c7" not in restricoes_removidas:
        c7 = m.addConstrs(
            w[s,disciplinas[d].curso] >= x[d,s,h] for d in disciplinas for s in salasLista for h in disciplinas[d].horarios_agrupamento()
        )

    # Indica as duplas de salas alocadas para um mesmo curso  que serão usadas no somatório de distância de salas alocadas a determinado curso
    if "c8" not in restricoes_removidas:
        c8 = m.addConstrs(
            t[si,sj,c] >= (w[si,c]+w[sj,c] - 1) for si in salasLista for sj in salasLista if salasLista.index(si) < salasLista.index(sj) for c in cursos
        )

    return ModeloAlocacao(
        modelo=m,
        instancia=instancia,
        x=x,
        y=y,
        w=w,
        t=t,
        z=z,
        v=v,
        restricoes_removidas=restricoes_removidas,
        resumo_lns=resumo_lns,
        disciplinas_livres=disciplinas_livres,
    )


def resolver_modelo(modelo_alocacao, parametros_gurobi=None, arquivo_solucao=None):
    parametros_gurobi = parametros_gurobi or {}
    m = modelo_alocacao.modelo
    
    m.setParam("TimeLimit", 25200) # Tempo limite de 7 horas
    for parametro, valor in parametros_gurobi.items():
        m.setParam(parametro, valor)
    m.optimize()

    if arquivo_solucao and m.SolCount > 0:
        m.write(arquivo_solucao)

    solucao_x = extrair_solucao_x(modelo_alocacao.x) if m.SolCount > 0 else None

    # # Para utilizar solução salva :
    # m.Params.MIPGap = 0.05
    # m.update()
    # m.read("solution.sol")
    # m.optimize()

    if m.status == gp.GRB.OPTIMAL:
        print("Solução ótima encontrada.")       
    else:
        print("Solução -> não <- ótima.")


    return {
        "status": m.status,
        "status_nome": _nome_status(m.status),
        "solucoes": m.SolCount,
        "objetivo": m.ObjVal if m.SolCount > 0 else None,
        "bound": m.ObjBound if m.SolCount > 0 else None,
        "gap": m.MIPGap if m.SolCount > 0 else None,
        "tempo": m.Runtime,
        "restricoes_removidas": sorted(modelo_alocacao.restricoes_removidas),
        "parametros_gurobi": parametros_gurobi,
        "arquivo_solucao": arquivo_solucao if m.SolCount > 0 else None,
        "solucao_x": solucao_x,
        "lns": modelo_alocacao.resumo_lns,
        "disciplinas_livres": sorted(modelo_alocacao.disciplinas_livres),
    }


def gerar_planilhas_saida(modelo_alocacao):
    instancia = modelo_alocacao.instancia
    conflitos = VerificaSolucao(
        instancia.disciplinas,
        instancia.salas,
        instancia.horarios,
        modelo_alocacao.x,
    ).verifica_conflito_turno()

    GeraPlanilhaSaida(
        instancia.disciplinas,
        instancia.salas,
        instancia.horarios,
        modelo_alocacao.x,
        "./web/static/dados/",
        "planilha_alocacoes.xlsx",
    ).cria_tabela_alocacoes(conflitos)
    GeraPlanilhaSaida(
        instancia.disciplinas,
        instancia.salas,
        instancia.horarios,
        modelo_alocacao.x,
        "./web/static/dados/",
        "planilha_alocacoes.xlsx",
    ).exporta_alocacoes()


def main(
    arquivo_horarios,
    arquivo_salas,
    arquivo_salas_preferenciais,
    restricoes_removidas=None,
    parametros_gurobi=None,
    gerar_planilhas=True,
    arquivo_solucao=None,
    arquivo_solucao_incumbente=None,
    disciplinas_livres=None,
    fase_livre=None,
    curso_livre=None,
):
    instancia = carregar_instancia(
        arquivo_horarios,
        arquivo_salas,
        arquivo_salas_preferenciais,
    )

    solucao_incumbente_x = None
    if arquivo_solucao_incumbente:
        solucao_incumbente_x = parse_solucao_x(arquivo_solucao_incumbente)

    modelo_alocacao = construir_modelo(
        instancia,
        restricoes_removidas=restricoes_removidas,
        solucao_incumbente_x=solucao_incumbente_x,
        disciplinas_livres=disciplinas_livres,
        fase_livre=fase_livre,
        curso_livre=curso_livre,
    )

    resultado = resolver_modelo(
        modelo_alocacao,
        parametros_gurobi=parametros_gurobi,
        arquivo_solucao=arquivo_solucao,
    )

    if not gerar_planilhas:
        return resultado

    gerar_planilhas_saida(modelo_alocacao)
    return resultado


def _nome_status(status):
    nomes = {
        gp.GRB.OPTIMAL: "OPTIMAL",
        gp.GRB.TIME_LIMIT: "TIME_LIMIT",
        gp.GRB.INFEASIBLE: "INFEASIBLE",
        gp.GRB.INF_OR_UNBD: "INF_OR_UNBD",
        gp.GRB.UNBOUNDED: "UNBOUNDED",
        gp.GRB.SOLUTION_LIMIT: "SOLUTION_LIMIT",
        gp.GRB.INTERRUPTED: "INTERRUPTED",
    }
    return nomes.get(status, str(status))


def _parametros_json(valor):
    if not valor:
        return {}
    return json.loads(valor)


def _lista_csv(valor):
    return [item.strip() for item in valor.split(",") if item.strip()]


def _fase_livre(valor):
    if not valor:
        return None
    partes = [parte.strip() for parte in valor.replace(":", ",").split(",")]
    if len(partes) != 2 or not partes[0] or not partes[1]:
        raise argparse.ArgumentTypeError("Use o formato CURSO:FASE. Ex.: CC:1")
    return partes[0], int(partes[1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Executa o modelo de alocacao de salas.")
    parser.add_argument("--horarios", default="./dados/horarios_2024_1.xlsx")
    parser.add_argument("--salas", default="./dados/salas_2024_1.csv")
    parser.add_argument("--preferenciais", default="./dados/salas_preferenciais_2024.1.xlsx")
    parser.add_argument("--remover", default="", help="Restricoes a remover, separadas por virgula. Ex.: c5,c6")
    parser.add_argument("--parametros", default="{}", help='Parametros Gurobi em JSON. Ex.: {"TimeLimit": 300}')
    parser.add_argument("--sem-planilhas", action="store_true")
    parser.add_argument("--salvar-solucao", default="", help="Caminho para salvar a solucao .sol encontrada.")
    parser.add_argument("--solucao-incumbente", default="", help="Arquivo .sol usado como MIP start e base de fixacao.")
    parser.add_argument("--liberar-disciplinas", default="", help="Disciplinas livres, separadas por virgula.")
    parser.add_argument("--liberar-fase", type=_fase_livre, default=None, help="Fase livre no formato CURSO:FASE. Ex.: CC:1")
    parser.add_argument("--liberar-curso", default="", help="Curso inteiro livre. Ex.: CC")
    args = parser.parse_args()

    removidas = [item.strip() for item in args.remover.split(",") if item.strip()]
    resultado = main(
        args.horarios,
        args.salas,
        args.preferenciais,
        restricoes_removidas=removidas,
        parametros_gurobi=_parametros_json(args.parametros),
        gerar_planilhas=not args.sem_planilhas,
        arquivo_solucao=args.salvar_solucao or None,
        arquivo_solucao_incumbente=args.solucao_incumbente or None,
        disciplinas_livres=_lista_csv(args.liberar_disciplinas),
        fase_livre=args.liberar_fase,
        curso_livre=args.liberar_curso or None,
    )
    print("RESULTADO_JSON=" + json.dumps(resultado, ensure_ascii=False, sort_keys=True))
