#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from typing import Any

import loguru         as LG
import rich.logging   as RL
import rich.pretty    as RY
import rich.traceback as RT
import typer          as TR

from pyata.core import (
    Ctx, NoCtx, Solver, Eq, And, Or, Distinct, Vars, Metrics, Substitutions,
    Var, Unification, CtxRichRepr
)

RT.install()
LG.logger.configure(handlers=[dict(
    level="DEBUG",
    sink=RL.RichHandler(
        markup=True,
        show_path=False),
    format="{message}",)])


WALK_LEN_GAUGE_KEY = 'walk_len'
SUBSTITUTIONS_COUNTER_KEY = 'unifications'
max_gauge = [0]
substitutions = [0]

def install_metrics(ctx: Ctx) -> Ctx:
    # walk_len_gauge       = Metrics.Gauge  (0, WALK_LEN_GAUGE_KEY, skip_stats_timeseries=True)
    substitutions_counter = Metrics.Counter(0, SUBSTITUTIONS_COUNTER_KEY,
                                            skip_stats_timeseries=True)
    
    def walk_condensible_cb(ctx: Ctx, data: tuple[Var, Any, set[Var]]
                            ) -> tuple[Ctx, tuple[Var, Any, set[Var]]]:
        _, _, seen = data
        n = len(seen)
        walk_len_gauge(n)
        if n > max_gauge[0]:
            max_gauge[0] = n
        return ctx, data
    ctx = Substitutions.hook_walk_condensible(
        ctx, walk_condensible_cb)

    def unification_cb(ctx: Ctx, data: tuple[Any, Any]
                       ) -> tuple[Ctx, tuple[Any, Any]]:
        substitutions[0] = substitutions_counter(1)
        return ctx, data
    ctx = Substitutions.hook_substitution(ctx, unification_cb)

    return ctx


def main(n: int = 8) -> None:
    
    ctx, vars = Vars.fresh(NoCtx, int, n)
    
    goal = And(*(Or(*(Eq(v, i) for i in range(n))) for v in vars),
                Distinct(*vars))
    
    ctx = install_metrics(ctx)
    
    n_solutions = 0
    last_solution = None
    
    def per_sec_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
        LG.logger.info(
            f'n = {n_solutions} '
            f'walk_len_max: {max_gauge[0]} '
            f'substitutions: {substitutions[0]} '
            f'last_solution: {last_solution}')
        return ctx
    Metrics.Singleton().hook_ticks(per_sec_cb)
    
#    RY.pprint(CtxRichRepr(ctx))
#    RY.pprint(CtxRichRepr(Metrics.Singleton().ctx))
#    return
    
    solver = Solver.given(ctx, vars)
    
    for _, solution in solver(goal):
        n_solutions += 1
        last_solution = solution
    LG.logger.info(
        f'{n_solutions} solutions found. '
        f'walk_len_max: {max_gauge[0]} '
        f'substitutions: {substitutions[0]} '
        f'last_solution: {last_solution}')

TR.run(main)
