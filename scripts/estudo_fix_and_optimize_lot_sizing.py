"""Exemplo minimo de fix-and-optimize baseado em PLI.

Problema usado: lot sizing capacitado multi-item.

Por que este exemplo ajuda no alocador de salas?
    - aqui a variavel binaria principal e y[item, periodo];
    - no alocador, a variavel binaria principal e x[disciplina, sala, horario];
    - em ambos os casos, o fix-and-optimize fixa a maior parte das binarias
      no valor da solucao atual e libera apenas uma vizinhanca para o solver.

Referencias para estudar junto:
    - Gurobi facility.py e MIP starts:
      https://docs.gurobi.com/projects/examples/en/current/overview/starts.html
    - Lot sizing com PLI em Pyomo:
      https://ndcbe.github.io/optimization/notebooks/assignments/Pyomo2.html
    - Lindahl, Sorensen e Stidsen (2018), fix-and-optimize para timetabling:
      https://doi.org/10.1007/s10732-018-9371-3
"""

from dataclasses import dataclass

import gurobipy as gp
from gurobipy import GRB


@dataclass(frozen=True)
class LotSizingData:
    items: range
    periods: range
    demand: dict[tuple[int, int], float]
    capacity: dict[int, float]
    setup_cost: dict[tuple[int, int], float]
    production_cost: dict[tuple[int, int], float]
    holding_cost: dict[int, float]
    big_m: dict[tuple[int, int], float]


def small_instance() -> LotSizingData:
    items = range(3)
    periods = range(6)

    demand_rows = [
        [20, 10, 30, 10, 25, 15],
        [10, 25, 10, 30, 10, 20],
        [15, 15, 15, 15, 15, 15],
    ]
    setup_rows = [
        [80, 80, 90, 90, 80, 80],
        [75, 85, 75, 85, 75, 85],
        [60, 70, 60, 70, 60, 70],
    ]
    production_rows = [
        [2, 2, 2, 3, 3, 3],
        [3, 3, 2, 2, 2, 3],
        [2, 3, 3, 2, 3, 2],
    ]
    capacity = {0: 60, 1: 55, 2: 60, 3: 55, 4: 60, 5: 60}
    holding_cost = {0: 1.0, 1: 1.2, 2: 0.8}

    demand = {(i, t): demand_rows[i][t] for i in items for t in periods}
    setup_cost = {(i, t): setup_rows[i][t] for i in items for t in periods}
    production_cost = {
        (i, t): production_rows[i][t] for i in items for t in periods
    }

    # Um limite valido e simples: produzir no maximo toda a demanda restante.
    big_m = {
        (i, t): sum(demand[i, tau] for tau in periods if tau >= t)
        for i in items
        for t in periods
    }

    return LotSizingData(
        items=items,
        periods=periods,
        demand=demand,
        capacity=capacity,
        setup_cost=setup_cost,
        production_cost=production_cost,
        holding_cost=holding_cost,
        big_m=big_m,
    )


def build_model(
    data: LotSizingData,
    fixed_setup: dict[tuple[int, int], int] | None = None,
    mip_start: dict[tuple[int, int], int] | None = None,
    time_limit: float | None = None,
) -> tuple[gp.Model, gp.tupledict, gp.tupledict, gp.tupledict]:
    fixed_setup = fixed_setup or {}
    mip_start = mip_start or {}

    model = gp.Model("lot_sizing_fix_and_optimize_study")
    model.Params.OutputFlag = 0
    if time_limit is not None:
        model.Params.TimeLimit = time_limit

    y = model.addVars(data.items, data.periods, vtype=GRB.BINARY, name="setup")
    produce = model.addVars(data.items, data.periods, lb=0.0, name="produce")
    stock = model.addVars(data.items, data.periods, lb=0.0, name="stock")

    for key, value in fixed_setup.items():
        y[key].LB = value
        y[key].UB = value

    for key, value in mip_start.items():
        y[key].Start = value

    model.addConstrs(
        produce[i, t] <= data.big_m[i, t] * y[i, t]
        for i in data.items
        for t in data.periods
    )
    model.addConstrs(
        gp.quicksum(produce[i, t] for i in data.items) <= data.capacity[t]
        for t in data.periods
    )
    model.addConstrs(
        produce[i, t] - data.demand[i, t] == stock[i, t]
        for i in data.items
        for t in data.periods
        if t == 0
    )
    model.addConstrs(
        stock[i, t - 1] + produce[i, t] - data.demand[i, t] == stock[i, t]
        for i in data.items
        for t in data.periods
        if t > 0
    )

    model.setObjective(
        gp.quicksum(
            data.setup_cost[i, t] * y[i, t]
            + data.production_cost[i, t] * produce[i, t]
            + data.holding_cost[i] * stock[i, t]
            for i in data.items
            for t in data.periods
        ),
        GRB.MINIMIZE,
    )
    return model, y, produce, stock


def solve_model(
    data: LotSizingData,
    fixed_setup: dict[tuple[int, int], int] | None = None,
    mip_start: dict[tuple[int, int], int] | None = None,
    time_limit: float | None = None,
) -> dict:
    model, y, produce, stock = build_model(data, fixed_setup, mip_start, time_limit)
    model.optimize()

    if model.SolCount == 0:
        raise RuntimeError(f"Nenhuma solucao encontrada. Status Gurobi: {model.Status}")

    setup_solution = {
        (i, t): int(round(y[i, t].X)) for i in data.items for t in data.periods
    }
    production_solution = {
        (i, t): produce[i, t].X for i in data.items for t in data.periods
    }
    stock_solution = {
        (i, t): stock[i, t].X for i in data.items for t in data.periods
    }

    return {
        "objective": model.ObjVal,
        "status": model.Status,
        "setup": setup_solution,
        "produce": production_solution,
        "stock": stock_solution,
    }


def initial_solution(data: LotSizingData) -> dict:
    # Solucao inicial deliberadamente simples: permitir setup em todos os pares
    # item-periodo. O solver escolhe producao e estoque com essas binarias fixas.
    all_setups_on = {(i, t): 1 for i in data.items for t in data.periods}
    return solve_model(data, fixed_setup=all_setups_on)


def period_windows(periods: range, window_size: int, overlap: int) -> list[set[int]]:
    step = max(1, window_size - overlap)
    windows = []
    start = 0
    last_period = max(periods)

    while start <= last_period:
        end = min(start + window_size - 1, last_period)
        windows.append(set(range(start, end + 1)))
        start += step

    return windows


def fix_and_optimize(
    data: LotSizingData,
    incumbent: dict,
    window_size: int = 2,
    overlap: int = 1,
    passes: int = 2,
    subproblem_time_limit: float = 10.0,
) -> dict:
    best = incumbent
    windows = period_windows(data.periods, window_size, overlap)

    print(f"Inicial FO: objetivo = {best['objective']:.2f}")
    for pass_number in range(1, passes + 1):
        improved_in_pass = False
        print(f"\nPassada {pass_number}")

        for window in windows:
            fixed_setup = {
                (i, t): best["setup"][i, t]
                for i in data.items
                for t in data.periods
                if t not in window
            }
            candidate = solve_model(
                data,
                fixed_setup=fixed_setup,
                mip_start=best["setup"],
                time_limit=subproblem_time_limit,
            )

            accepted = candidate["objective"] < best["objective"] - 1e-6
            label = "aceita" if accepted else "sem melhora"
            print(
                f"  janela periodos {sorted(window)}: "
                f"{candidate['objective']:.2f} ({label})"
            )

            if accepted:
                best = candidate
                improved_in_pass = True

        if not improved_in_pass:
            break

    return best


def print_solution(data: LotSizingData, solution: dict, title: str) -> None:
    print(f"\n{title}")
    print(f"Objetivo: {solution['objective']:.2f}")
    for i in data.items:
        setups = " ".join(str(solution["setup"][i, t]) for t in data.periods)
        production = " ".join(f"{solution['produce'][i, t]:5.1f}" for t in data.periods)
        stock = " ".join(f"{solution['stock'][i, t]:5.1f}" for t in data.periods)
        print(f"  item {i} setup:    {setups}")
        print(f"  item {i} producao: {production}")
        print(f"  item {i} estoque:  {stock}")


def main() -> None:
    data = small_instance()

    start = initial_solution(data)
    best_fo = fix_and_optimize(data, start)
    full_mip = solve_model(data)

    print_solution(data, start, "Solucao inicial")
    print_solution(data, best_fo, "Solucao apos fix-and-optimize")
    print_solution(data, full_mip, "Otimo do PLI completo nesta instancia pequena")

    gap = 100 * (best_fo["objective"] - full_mip["objective"]) / full_mip["objective"]
    print(f"\nGap FO vs PLI completo: {gap:.2f}%")


if __name__ == "__main__":
    main()
