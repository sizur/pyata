#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc import ABC
from typing import Any, Callable, ClassVar, Final, Iterator, Self

import rich.repr as RR

from .Constraints import Constraints
from .Facets import FacetABC, FacetRichReprMixin, CtxRichRepr
from .Metrics import Metrics
from .Types  import Ctx, NoCtx, Goal, HookEventCB, RichReprable
from .Vars   import Var, Vars, SymAssumps, Substitutions


__all__: list[str] = [
    'SolverABC', 'SolverGiven', 'SolverFresh', 'SolverRunner'
]

SUBS_COUNT: Final[str] = 'subs_count'


class SolverRichReprCtxMixin(ABC, RichReprable):
    ctx : Ctx
    def __rich_repr__(self: Self) -> RR.Result:
        yield CtxRichRepr(self.ctx)


class SolverABC(ABC):
    vars: tuple[Var, ...]
    ctx : Ctx

    def instrument(self: Self, cb: Callable[[Ctx], Ctx]) -> Self:
        self.ctx = cb(self.ctx)
        return self
    
    def prep_ctx(self: Self) -> None:
        # Extend the context with constraints functionaality.
        self.ctx = Constraints.install(self.ctx)
        
        # Maarking each new state (with a new subtitution)
        # with a total substitutions count
        # -- a basic measure of steps taken.
        subs_counter = Metrics.Counter(
            0, (self, 'subs_counter'), skip_stats_timeseries=True)
        def subs_cb(ctx: Ctx, data: tuple[Var, Any]
                    ) -> tuple[Ctx, tuple[Var, Any]]:
            total = subs_counter(1)
            ctx = SolverCtxState.set(ctx, SUBS_COUNT, total)
            return ctx, data
        self.ctx = Substitutions.hook_substitution(
            self.ctx, subs_cb)
    
    def hook_per_sec(self: Self, cb: HookEventCB[tuple[int, float]]) -> None:
        # NOTE: Switching contexts from Metrics to Solver and back.
        def ctx_switched_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            self.ctx = cb(self.ctx, data)
            return ctx
        Metrics.Singleton().hook_ticks(ctx_switched_cb)

class SolverGiven(SolverABC):
    def __init__(self: Self, ctx: Ctx, vars: tuple[Var, ...]) -> None:
        self.vars = vars
        self.ctx  = ctx
        self.prep_ctx()
    
    def __call__(self: Self, goal: Goal) -> SolverRunner:
        return SolverRunner(self.ctx, self.vars, goal)


class SolverFresh(SolverABC):
    
    def __init__(self: Self,
        typ: type | None = None,
        num: int  | None = None,
        ctx: Ctx  | None = None,
        /,
        **kwargs: SymAssumps
    ) -> None:
        ctx = ctx if ctx else NoCtx
        ctx, self.vars = Vars.fresh(ctx, typ, num, **kwargs)
        self.prep_ctx()
    
    def __call__(self: Self, goal: Goal) -> SolverRunner:
        return SolverRunner(self.ctx, self.vars, goal)


class SolverRunner(SolverABC, SolverRichReprCtxMixin):
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

    def __next__(self: Self) -> tuple[Any, ...]:
        self.ctx = next(self.stream_iter)
        self.ctx, vars = Vars.walk_and_classify_vars(
            self.ctx, self.vars)
        return vars

    def steps_taken(self: Self) -> int:
        return SolverCtxState.get(self.ctx, SUBS_COUNT)


class SolverCtxState(FacetABC[Any, Any], FacetRichReprMixin[Any]):
    default: ClassVar[Any] = None
