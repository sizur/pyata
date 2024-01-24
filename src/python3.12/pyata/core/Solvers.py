#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc import ABC
from typing import Any, Callable, Iterator, Self

from .Constraints import Constraints
from .Types  import Ctx, NoCtx, Goal
from .Vars   import Var, Vars, SymAssumps


__all__: list[str] = [
    'Solver', 'SolverGiven', 'SolverLauncher', 'SolverRunner'
]


class Solver:
    def __new__(cls: type[Self],
        typ: type | None = None,
        num: int  | None = None,
        ctx: Ctx  | None = None,
        /,
        **kwargs: SymAssumps
    ) -> SolverLauncher:
        return SolverLauncher(typ, num, ctx, **kwargs)
    
    def __init__(self: Self,
        typ: type | None = None,
        num: int  | None = None,
        ctx: Ctx  | None = None,
        /,
        **kwargs: SymAssumps
    ) -> None: pass

    @staticmethod
    def given(ctx: Ctx, vars: tuple[Var, ...]) -> SolverGiven:
        return SolverGiven(ctx, vars)


class SolverABC(ABC):
    vars  : tuple[Var, ...]
    ctx   : Ctx

    def instrument(self: Self, cb: Callable[[Ctx], Ctx]) -> Self:
        self.ctx = cb(self.ctx)
        return self


class SolverGiven(SolverABC):
    def __init__(self: Self, ctx: Ctx, vars: tuple[Var, ...]) -> None:
        self.vars = vars
        self.ctx = Constraints.install(ctx)
    
    def __call__(self: Self, goal: Goal) -> SolverRunner:
        return SolverRunner(self.ctx, self.vars, goal)


class SolverLauncher(SolverABC):
    
    def __init__(self: Self,
        typ: type | None = None,
        num: int  | None = None,
        ctx: Ctx  | None = None,
        /,
        **kwargs: SymAssumps
    ) -> None:
        ctx = ctx if ctx else NoCtx
        ctx, self.vars = Vars.fresh(ctx, typ, num, **kwargs)
        self.ctx = Constraints.install(ctx)
    
    def __call__(self: Self, goal: Goal) -> SolverRunner:
        return SolverRunner(self.ctx, self.vars, goal)


class SolverRunner(SolverABC):
    stream_iter: Iterator[Ctx]
    goal: Goal
    
    def __init__(self: Self,
        ctx: Ctx,
        vars: tuple[Var, ...],
        goal: Goal
    ) -> None:
        self.ctx  = ctx
        self.vars = vars
        self.goal = goal
        self.stream_iter = iter(goal(ctx))
    
    def __iter__(self: Self) -> Self:
        return self

    def __next__(self: Self) -> tuple[Ctx, tuple[Any, ...]]:
        self.ctx = next(self.stream_iter)
        return Vars.walk_and_type_vars(self.ctx, self.vars)

