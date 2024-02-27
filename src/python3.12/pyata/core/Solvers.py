#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc import ABC
from typing import Any, Callable, ClassVar, Final, Iterator, Self

import rich
import rich.pretty, rich.repr

from .Constraints import Constraints
from .Facets import FacetABC, FacetRichReprMixin, CtxRichRepr, \
    HooksEvents, HooksPipelines, HooksBroadcasts
from .Metrics import Metrics
from .Types  import Ctx, NoCtx, Var, Goal, HookEventCB, HookPipelineCB, \
    HookBroadcastCB, RichReprable, CtxSized, BroadcastKey
from .Vars   import Vars, SymAssumps, Substitutions


__all__: list[str] = [
    'SolverABC', 'Solver'
]

SUBS_COUNT: Final[str] = 'subs_count'


class SolverRichReprCtxMixin(ABC, RichReprable):
    ctx : Ctx
    def __rich_repr__(self: Self) -> rich.repr.Result:
        yield CtxRichRepr(self.ctx)


class SolverABC(ABC):
    ctx        : Ctx
    vars       : tuple[Var, ...]
    goal       : Goal
    metrics    : Metrics
    steps_count: int
    
    _step_tag_ctx: bool
    _skip_step_stats_timeseries: bool
    
    def __init__(self: Self,
                 ctx: Ctx,
                 vars: tuple[Var, ...],
                 goal: Goal,
                 /,
                 metrics: Metrics | None = None,
                 # perf/data trade-offs
                 step_tag_ctx: bool = False,
                 skip_step_stats_timeseries: bool = True,
                 **kwargs: Any
    ) -> None:
        self.ctx = ctx
        self.vars = vars
        self.goal = goal
        self.metrics = metrics if metrics else Metrics.Singleton()
        self.steps_count = 0
        self._step_tag_ctx = step_tag_ctx
        self._skip_step_stats_timeseries = skip_step_stats_timeseries
        self.__pyata_solver_pre_init__()

    def instrument(self: Self, cb: Callable[[Ctx], Ctx]) -> None:
        self.ctx = cb(self.ctx)

    def hook_event(self: Self, key: Any, cb: HookEventCB[Any]) -> None:
        self.instrument(lambda ctx: HooksEvents.hook(ctx, key, cb))
    
    def hook_pipeline(self: Self, key: Any, cb: HookPipelineCB[Any]
                      ) -> None:
        self.instrument(lambda ctx: HooksPipelines.hook(ctx, key, cb))
    
    def hook_broadcast(self: Self, key: BroadcastKey, cb: HookBroadcastCB[Any]
                       ) -> None:
        self.instrument(lambda ctx: HooksBroadcasts.hook(ctx, key, cb))
    
    def __pyata_solver_pre_init__(self: Self) -> None:
        # Extend the context with constraints functionaality.
        self.ctx = Constraints.install(self.ctx)
        
        # NOTE: At least one sensor is required for per_sec hooking,
        #       enabling a live inspection or even modification of
        #       the running solver's state.
        # Counting substitution steps -- a basic measure of steps taken
        # in the search space.
        subs_counter = Metrics.Counter[int](0,
            key=(self, SUBS_COUNT),
            metrics=self.metrics,
            skip_stats_timeseries=self._skip_step_stats_timeseries)
        if self._step_tag_ctx:
            # Maarking each new state (with a new subtitution)
            # with a total substitutions count
            def subs_cb(ctx: Ctx, data: tuple[Var, Any]
                        ) -> tuple[Ctx, tuple[Var, Any]]:
                self.steps_count = subs_counter(1)
                ctx = SolverCtxTags.set(ctx, SUBS_COUNT, self.steps_count)
                self.ctx = ctx
                return ctx, data
        else:
            def subs_cb(ctx: Ctx, data: tuple[Var, Any]
                        ) -> tuple[Ctx, tuple[Var, Any]]:
                self.steps_count = subs_counter(1)
                self.ctx = ctx
                return ctx, data
        self.ctx = Substitutions.hook_substitution(
            self.ctx, subs_cb)
        self.__pyata_solver_init__()
    
    def __pyata_solver_init__(self: Self) -> None:
        pass
    
    def hook_per_sec(self: Self, cb: HookEventCB[tuple[int, float]]) -> None:
        def ctx_switched_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            # NOTE: The callback will expect the Solver's context, so
            #       switching contexts from Metrics to Solver and back
            #       since per_sec hooking are processed by the Metrics,
            #       which holds its own context, just like the Solver.
            self.ctx = cb(self.ctx, data)
            return ctx
        self.metrics.hook_ticks(ctx_switched_cb)


class Solver(SolverABC, SolverRichReprCtxMixin):
    stream_iter: Iterator[Ctx]
    latest_solution_ctx: Ctx | None
    
    def __pyata_solver_init__(self: Self) -> None:
        super().__pyata_solver_init__()
        # self.stream_iter = iter(self.goal(self.ctx))
        self.latest_solution_ctx = None
    
    @classmethod
    def Fresh(
        cls: type[Self],
        goal: Goal,
        typ: type | None = None,
        num: int  | None = None,
        ctx: Ctx  | None = None,
        /,
        **kwargs: Any
    ) -> Solver:
        """Alternative constructor for Solver, with fresh variables."""
        ctx = ctx if ctx else NoCtx
        assumps = {k: v for k, v in kwargs.items()
                   if k in SymAssumps.__optional_keys__}
        kwargs = {k: v for k, v in kwargs.items()
                  if k not in SymAssumps.__optional_keys__}
        ctx, vars = Vars.fresh(ctx, typ, num, **assumps)
        return cls(ctx, vars, goal, **kwargs)
    
    def __iter__(self: Self) -> Self:
        self.stream_iter = iter(self.goal(self.ctx))
        return self

    def __next__(self: Self) -> tuple[Any, ...]:
        self.ctx = next(self.stream_iter)
        self.latest_solution_ctx = self.ctx
        self.ctx, sol = self.__solution__()
        return sol
    
    def size(self: Self) -> int:
        if isinstance(self.goal, CtxSized):
            return self.goal.__ctx_len__(self.ctx)
        raise NotImplementedError
    
    def latest_solution(self: Self) -> tuple[Any, ...] | None:
        if self.latest_solution_ctx is None:
            return None
        curr_ctx = self.ctx
        ret = None
        try:
            self.ctx = self.latest_solution_ctx
            _, ret = self.__solution__()
        finally:
            self.ctx = curr_ctx
        return ret
    
    def __solution__(self: Self) -> tuple[Ctx, tuple[Any, ...]]:
        """Subclasses can specialize this method to extract required tuple type from the context."""
        return Vars.walk_reify_vars(
            self.ctx, self.vars)
    
    def get_ctx_repr_for(self: Self, obj: Any) -> str:
        _, ret = obj.__ctx_self_rich_repr__(self.ctx)
        return rich.pretty.pretty_repr(ret)


class SolverCtxTags(FacetABC[Any, Any], FacetRichReprMixin[Any]):
    default: ClassVar[Any] = None
