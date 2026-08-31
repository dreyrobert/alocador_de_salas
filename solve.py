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
    parse_solucao_x,
)
import argparse
import json
import gurobipy as gp
from gurobipy import GRB

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
    restricoes_removidas = set(restricoes_removidas or [])
    parametros_gurobi = parametros_gurobi or {}

    salas = ExtraiSalas(arquivo_salas).extrai_salas()
    salasLista = list(salas.keys())
    matriz_dist = GeraMatrizDistancia(salas).gera_matriz()
    disciplinas,horarios,fases,cursos = ExtraiHorariosAula(arquivo_horarios,arquivo_salas_preferenciais).extrai_horarios_aula()

    disciplinas_livres = set(disciplinas_livres or [])
    if fase_livre:
        curso, fase = fase_livre
        disciplinas_livres.update(disciplinas_da_fase(disciplinas, curso, fase))
    if curso_livre:
        disciplinas_livres.update(disciplinas_do_curso(disciplinas, curso_livre))
 
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

    resumo_lns = None
    if arquivo_solucao_incumbente:
        solucao_incumbente_x = parse_solucao_x(arquivo_solucao_incumbente)
        if disciplinas_livres:
            resumo_lns = aplicar_start_e_fixacao_x(
                x,
                solucao_incumbente_x,
                disciplinas_livres,
            )
        else:
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
    
    m.setParam('VarsName', 1)
    m.setParam(GRB.Param.TimeLimit, 25200) # Tempo limite de 7 horas
    for parametro, valor in parametros_gurobi.items():
        m.setParam(parametro, valor)
    m.optimize()

    if arquivo_solucao and m.SolCount > 0:
        m.write(arquivo_solucao)

    # # Para utilizar solução salva :
    # m.Params.MIPGap = 0.05
    # m.update()
    # m.read("solution.sol")
    # m.optimize()

    if m.status == gp.GRB.OPTIMAL:
        print("Solução ótima encontrada.")       
    else:
        print("Solução -> não <- ótima.")


    resultado = {
        "status": m.status,
        "status_nome": _nome_status(m.status),
        "solucoes": m.SolCount,
        "objetivo": m.ObjVal if m.SolCount > 0 else None,
        "bound": m.ObjBound if m.SolCount > 0 else None,
        "gap": m.MIPGap if m.SolCount > 0 else None,
        "tempo": m.Runtime,
        "restricoes_removidas": sorted(restricoes_removidas),
        "parametros_gurobi": parametros_gurobi,
        "arquivo_solucao": arquivo_solucao if m.SolCount > 0 else None,
        "lns": resumo_lns,
        "disciplinas_livres": sorted(disciplinas_livres),
    }

    if not gerar_planilhas:
        return resultado

    conflitos = VerificaSolucao(disciplinas,salas,horarios,x).verifica_conflito_turno()

    GeraPlanilhaSaida(disciplinas,salas,horarios,x,"./web/static/dados/","planilha_alocacoes.xlsx").cria_tabela_alocacoes(conflitos)
    GeraPlanilhaSaida(disciplinas,salas,horarios,x,"./web/static/dados/","planilha_alocacoes.xlsx").exporta_alocacoes()
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
