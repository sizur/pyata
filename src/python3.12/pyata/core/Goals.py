#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sized
from math import prod
from more_itertools import interleave_longest
from typing import Any, Self

import rich, \
    scipy          # type: ignore
import rich.pretty, rich.repr, \
    scipy.special  # pyright: ignore[reportMissingTypeStubs]

from .Constraints import PositiveCardinalityProduct
from .Facets      import (HooksPipelines, HookPipelineCB)
from .Types       import (Var, Ctx, Goal, GoalVared, GoalCtxSized,
                          GoalCtxSizedVared, Constraint, Stream,
                          Connective, MaybeCtxSized, RichReprable,
                          CtxSelfRichReprable, Named
                          )
from .Unification import Unification
from .Vars        import Vars
from ..immutables import Map, Set


__all__: list[str] = [
    'GoalABC', 'Succeed', 'Fail', 'Eq', 'Goal'
]


mconcat = interleave_longest


def mbind(stream: Stream, goal: Goal) -> Stream:
    for ctx in stream:
        yield from goal(ctx)


class GoalABC(ABC, Goal, Named, CtxSelfRichReprable):
    name: str
    RichReprDecor: type[RichReprable]
    
    def __init__(self: Self, *, name: str | None = None) -> None:
        if name is None:
            try:
                self.name = self.__name__
            except AttributeError:
                try:
                    self.name = self.__class__.__name__
                except AttributeError as e:
                    raise TypeError(
                        f'Cannot infer name for {self!r}. '
                    ) from e
        else:
            self.name = name
    
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Stream:
        raise NotImplementedError

    def __rich_repr__(self: Self) -> rich.repr.Result:
        if self.name:
            yield self.name
        if isinstance(self, GoalVared):
            for var in self.vars:
                yield var
    
    def __init_subclass__(cls: type, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class RichRepr[C: GoalABC](RichReprable):
            def __init__(self: Self, ego: C, ctx: Ctx) -> None:
                self.ego: C   = ego
                self.ctx: Ctx = ctx
            
            def __rich_repr__(self: Self) -> rich.repr.Result:
                ctx, ego = self.ctx, self.ego
                if hasattr(ego, 'name'):
                    yield ego.name
                if isinstance(ego, GoalCtxSized):
                    yield ego.__ctx_len__(ctx)
                elif isinstance(ego, Sized):
                    yield ego.__len__()
                if isinstance(ego, GoalVared):
                    for var in ego.vars:
                        ctx, val = Vars.walk_reify(ctx, var)
                        if var == val:
                            yield var
                        else:
                            yield rich.pretty.pretty_repr(var), val
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecor = RichRepr
    
    def __ctx_self_rich_repr__(self: Self, ctx: Ctx
                               ) -> tuple[Ctx, RichReprable]:
        return ctx, self.RichReprDecor(self, ctx)
    
    def progress(self: Self, cur: int, tot: int) -> None:
        pass


class Succeed(GoalABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        yield ctx


class Fail(GoalABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        return
        yield


class Eq(GoalABC):
    a: Any
    b: Any
    
    def __init__(self: Self, a: Any, b: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.a = a
        self.b = b

    def __call__(self: Self, ctx: Ctx) -> Stream:
        ctx = Unification.unify(ctx, self.a, self.b)
        if ctx is Unification.Failed:
            return
        yield ctx
    
    def __rich_repr__(self: Self) -> rich.repr.Result:
        yield self.a
        yield self.b


class ConnectiveABC(GoalABC, Connective, ABC):
    goals: tuple[Goal, ...]
    constraints: tuple[Constraint, ...]
    RichReprDecor: type[RichReprable]
    
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        goals: list[Goal] = []
        constraints: list[Constraint] = []
        for g_c in g_or_c:
            if isinstance(g_c, Constraint):
                constraints.append(g_c)
            else:
                goals.append(g_c)
        self.constraints = tuple(constraints)
        self.goals = (goal, *goals)
        self.var_to_goals = Map[Var, Set[GoalVared]]()
        
        if (isinstance(self, MaybeCtxSized)
            and any(isinstance(g, GoalCtxSized) for g in self.goals)):
            # This check is needed for composable nested connectives
            # to propagate Sized-ness when possible.
            self.__ctx_len__ = self.__maybe_ctx_len__
        
        # Vared duck-type
        vars: list[Var] = []
        for goal in self.goals:
            if isinstance(goal, GoalVared):
                for var in goal.vars:
                    if var not in vars:
                        vars.append(var)
        if vars:
            self.vars: tuple[Var, ...] = tuple(vars)
    
    def get_vars_entanglement_vec(self: Self) -> list[int]:
        return [len(self.var_to_goals[var]) for var in self.vars]

    def __call__(self: Self, ctx: Ctx) -> Stream:
        for constraint in self.constraints:
            ctx = constraint.constrain(ctx)
        return self._compose_goals(*HooksPipelines.run(
            ctx, type(self).hook_heuristic, self.goals))
    
    @classmethod
    @abstractmethod
    def _compose_goals(cls: type[Self], ctx: Ctx,
                       goals: tuple[Goal, ...]
    ) -> Stream:
        raise NotImplementedError
    
    @classmethod
    def hook_heuristic(cls: type[Self], ctx: Ctx,
                       cb: HookPipelineCB[tuple[Goal, ...]]
    ) -> Ctx:
        return HooksPipelines.hook(ctx, cls.hook_heuristic, cb)
    
    def __rich_repr__(self: Self) -> rich.repr.Result:
        for constraint in self.constraints:
            yield constraint
        for goal in self.goals:
            yield goal
    
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        # super().__init_subclass__(**kwargs)
        class RichRepr[C: ConnectiveABC](RichReprable):
            def __init__(self: Self, ego: C, ctx: Ctx) -> None:
                self.ego: C   = ego
                self.ctx: Ctx = ctx
            
            def __rich_repr__(self: Self) -> rich.repr.Result:
                ctx, ego = self.ctx, self.ego
                constraint_reprs: list[Any] = []
                for constraint in ego.constraints:
                    if isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
                        constraint, CtxSelfRichReprable
                    ):
                        ctx, crepr = constraint.__ctx_self_rich_repr__(ctx)
                    elif isinstance(constraint, RichReprable):
                        crepr = constraint.__rich_repr__()
                    else:
                        crepr = constraint
                    constraint_reprs.append(crepr)
                if constraint_reprs:
                    yield constraint_reprs
                for goal in ego.goals:
                    if isinstance(goal, CtxSelfRichReprable):
                        ctx, grepr = goal.__ctx_self_rich_repr__(ctx)
                    elif isinstance(goal, RichReprable):
                        grepr = goal.__rich_repr__()
                    else:
                        grepr = goal
                    yield grepr
                if ego.var_to_goals:
                    yield 'constraining_vars', ego.var_to_goals
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecor = RichRepr
    
    def __ctx_self_rich_repr__(self: Self, ctx: Ctx) -> tuple[Ctx, RichReprable]:
        return ctx, self.RichReprDecor(self, ctx)

######################################################################
#  TODO: Utilize the engine itself to optimize the search order.
#        Recursively if needed.  Goal is to use var dependencies to
#        find smallest overall search space.
######################################################################

class And(ConnectiveABC, MaybeCtxSized):
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint,
                    **kwargs: Any) -> None:
        super().__init__(goal, *g_or_c, **kwargs)
        if any(isinstance(g, GoalCtxSizedVared) for g in self.goals):
            self.distribution: dict[Var, dict[Any, int]] = defaultdict(
                lambda: defaultdict(int))
            for goal in self.goals:
                if isinstance(goal, GoalCtxSizedVared):
                    for var, distrib in goal.distribution.items():
                        for val, num in distrib.items():
                            self.distribution[var][val] += num
        var_to_goals: dict[Var, set[GoalCtxSizedVared]] = defaultdict(set)
        for goal in [g for g in self.goals
                     if isinstance(g, GoalCtxSizedVared)]:
            for var in goal.vars:
                var_to_goals[var].add(goal)
        cardinality_constraints: list[PositiveCardinalityProduct] = []
        for var, goals in var_to_goals.items():
            cardinality_constraints.append(
                PositiveCardinalityProduct((var,), tuple(goals)))
        self.constraints = (*self.constraints, *cardinality_constraints)
    
    @classmethod
    def _compose_goals(cls: type[Self], ctx: Ctx,
                       goals: tuple[Goal, ...]
    ) -> Stream:
        stream: Stream = goals[0](ctx)
        for goal in goals[1:]:
            stream = mbind(stream, goal)
        return stream
    
    def __maybe_ctx_len__(self: Self, ctx: Ctx) -> int:
        return prod(g.__ctx_len__(ctx)
                    for g in self.goals
                    if isinstance(g, GoalCtxSized))

    @staticmethod
    def heur_conj_chain_vars(
        ctx: Ctx,
        data: tuple[Goal, ...],
    ) -> tuple[Ctx, tuple[Goal, ...]]:
        goals = data
        varedsized = [g for g in goals if isinstance(g, GoalCtxSizedVared)]
        others = [g for g in goals if not isinstance(g, GoalCtxSizedVared)]
        sizes = {g: g.__ctx_len__(ctx) for g in varedsized}
        var_to_goals: dict[Var, set[GoalCtxSizedVared]] = defaultdict(set)
        for goal in varedsized:
            for var in goal.vars:
                var_to_goals[var].add(goal)
        entanglements = {g: prod(len(var_to_goals[var]) for var in g.vars)
                        for g in varedsized}
        def order_key(goal: GoalCtxSizedVared) -> float:
            return sizes[goal] / entanglements[goal]
        varedsized.sort(key=order_key)
        staged: set[GoalCtxSizedVared] = set()
        for i in range(len(varedsized) - 2):
            goal = varedsized[i]
            proced = varedsized[0:i+1]
            staged = staged.union(g for v in goal.vars for g in var_to_goals[v]
                                if g not in proced)
            staged.discard(goal)
            # if chain is broken, we act as if remaining goals were staged
            # for the iteration.
            if not staged:
                staged_ = set(varedsized[i+1:])
            else:
                staged_ = staged
            assert len(staged_) > 0
            ix_staged = [ix for ix in range(i + 1, len(varedsized))
                        if varedsized[ix] in staged_]
            ix_staged.sort(key=lambda ix: order_key(varedsized[ix]))
            ix0 = ix_staged[0]
            ix = i + 1
            if ix != ix0:
                varedsized[ix], varedsized[ix0] = varedsized[ix0], varedsized[ix]
        # TODO: run a broadcast or event hook
        return ctx, tuple(varedsized + others)

class Or(ConnectiveABC, MaybeCtxSized):
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint,
                    **kwargs: Any) -> None:
            super().__init__(goal, *g_or_c, **kwargs)
            if any(isinstance(g, GoalCtxSizedVared) for g in self.goals):
                self.distribution: dict[Var, dict[Any, int]] = defaultdict(
                    lambda: defaultdict(int))
                for goal in self.goals:
                    if isinstance(goal, GoalCtxSizedVared):
                        for var, distrib in goal.distribution.items():
                            for val, num in distrib.items():
                                self.distribution[var][val] += num
    
    @classmethod
    def _compose_goals(cls: type[Self], ctx: Ctx,
                       goals: tuple[Goal, ...]
    ) -> Stream:
        return mconcat(*(goal(ctx) for goal in goals))

    def __maybe_ctx_len__(self: Self, ctx: Ctx) -> int:
        return sum(g.__ctx_len__(ctx)
                   for g in self.goals
                   if isinstance(g, GoalCtxSized))
