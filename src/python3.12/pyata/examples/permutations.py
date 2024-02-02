#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations

import loguru         as LG
import rich.live      as RV
import rich.logging   as RL
import rich.panel     as RP
import rich.pretty    as RY
import rich.traceback as RT
import typer          as TR

from pyata.core import (
    Ctx, NoCtx, Solver, Eq, And, Or, Distinct, Vars
)

RT.install()
LG.logger.configure(handlers=[dict(
    level="DEBUG",
    sink=RL.RichHandler(
        markup=True,
        show_path=False,),
    format="{message}",)])

def main(n: int = 9) -> None:
    
    ctx, vars = Vars.fresh(NoCtx, int, n)
    
    goal = And(*(Or(*(Eq(v, i) for i in range(n))) for v in vars),
                Distinct(*vars))
    
    solver = Solver(ctx, vars, goal)
    
    n_solutions = 0
    latest_solution = None
    
    with RV.Live(RP.Panel.fit(RY.Pretty(solver)),
                 auto_refresh=False,
                 transient=True
    ) as live:
        
        def per_sec_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            LG.logger.info(f'Solution {n_solutions}: {latest_solution}')
            live.update(
                RP.Panel.fit(RY.Pretty(dict(
                    steps_taken     = solver.steps_count,
                    n_solutions     = n_solutions,
                    latest_solution = latest_solution,
                    solver_state    = solver))),
                refresh=True)
            return ctx
        solver.hook_per_sec(per_sec_cb)
    
        # Solve
        for solution in solver:
            n_solutions += 1
            latest_solution = solution
            
    LG.logger.info(f'{n_solutions} solutions found.')

TR.run(main)
