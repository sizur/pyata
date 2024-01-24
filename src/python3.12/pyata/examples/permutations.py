#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations

import loguru         as LG
import rich.logging   as RL
import rich.repr      as RR
import rich.pretty    as RY
import rich.traceback as RT
import typer          as TR

from pyata.core import NoCtx, Solver, Eq, And, Or, Distinct, Vars


def main(n: int = 9) -> None:
    
    ctx, vars = Vars.fresh(NoCtx, int, n)
    
    goal = And(*(Or(*(Eq(v, i) for i in range(n))) for v in vars),
                Distinct(*vars))
    
    solver= Solver.given(ctx, vars)
    
    every_n = 1000
    i = 0
    for _, solution in solver(goal):
        i += 1
        if i % every_n == 0:
            print(f'{i}: {solution}')
    print(f'{i} solutions found.')

TR.run(main)
