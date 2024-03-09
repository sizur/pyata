#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from collections import defaultdict
import collections.abc as AB
from itertools import chain
from math import prod
from more_itertools import interleave_longest
from typing import Any, Iterable, Self

import rich, \
    scipy          # type: ignore
import rich.pretty, rich.repr, \
    scipy.special  # pyright: ignore[reportMissingTypeStubs]

from .Constraints import PositiveCardinalityProduct
from .Facets      import ( HooksPipelines, HookPipelineCB
                         , Installations )
from .Types       import (Var, Ctx, Goal, GoalVared, GoalCtxSized,
                          GoalCtxSizedVared, Constraint, Stream,
                          Connective, MaybeCtxSized, RichReprable,
                          CtxSelfRichReprable, Named, CtxInstallable)
from .Unification import Unification
from .Vars        import Vars, Substitutions
from ..immutables import Map, Set

__all__: list[str] = [
    'GoalABC', 'Succeed', 'Fail', 'Eq', 'Goal', 'And', 'Or',
    'HeurConjChainVars', 'HeurConjCardinality',
    'ConjunctiveHeuristic', 'DisjunctiveHeuristic',
    'discern_goals', 'discriminate_goals',
]

mconcat = interleave_longest

def mbind(stream: Stream, goal: Goal) -> Stream:
    for ctx in stream:
        yield from goal(ctx)

def discern_goals(
    goals: Iterable[Goal]
) -> tuple[list[GoalCtxSizedVared],
           list[GoalCtxSized],
           list[GoalVared]]:
    """Subsets of goals based on their includive trait categories."""
    return ([g for g in goals if isinstance(g, GoalCtxSizedVared)],
            [g for g in goals if isinstance(g, GoalCtxSized)],
            [g for g in goals if isinstance(g, GoalVared)])

def discriminate_goals(
    goals: Iterable[Goal]
) -> tuple[list[GoalCtxSizedVared],
           list[GoalCtxSized],
           list[GoalVared],
           list[Goal]]:
    """Partition goals into exclusive trait categories."""
    return ([g for g in goals if isinstance(g, GoalCtxSizedVared)],
            [g for g in goals if (isinstance(g, GoalCtxSized) and
                                  not isinstance(g, GoalVared))],
            [g for g in goals if (isinstance(g, GoalVared) and
                                  not isinstance(g, GoalCtxSized))],
            [g for g in goals if (not isinstance(g, GoalVared) and
                                  not isinstance(g, GoalCtxSized))])

class GoalABC(ABC, Goal, Named, CtxSelfRichReprable):
    name: str
    RichReprDecor: type[RichReprable]
    
    def __init__(self: Self, *, name: str | None = None) -> None:
        if name is None:
            try:
                self.name = self.__name__  # type: ignore
            except AttributeError:
                try:
                    self.name = self.__class__.__name__  # type: ignore
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
                elif isinstance(ego, AB.Sized):
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


class GoalVaredABC(GoalABC, GoalVared, ABC):
    vars: tuple[Var, ...]
    
    def get_ctx_vars(self: Self, ctx: Ctx
    ) -> Iterable[Var]:
        for var in self.vars:
            ctx, val = Substitutions.walk(ctx, var)
            if isinstance(val, Var):
                yield val


class Succeed(GoalABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        yield ctx


class Fail(GoalABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        return
        yield


class Eq(GoalVaredABC):
    a: Any
    b: Any
    
    def __init__(self: Self, a: Any, b: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.a = a
        self.b = b
        self.vars = tuple(v for v in (a, b) if isinstance(v, Var))

    def __call__(self: Self, ctx: Ctx) -> Stream:
        ctx = Unification.unify(ctx, self.a, self.b)
        if ctx is Unification.Failed:
            return
        yield ctx
    
    def __rich_repr__(self: Self) -> rich.repr.Result:
        yield self.a
        yield self.b


class ConnectiveABC(GoalVaredABC, Connective, ABC):
    goals: tuple[Goal, ...]
    constraints: tuple[Constraint, ...]
    var_to_goals: Map[Var, Set[GoalVared]]
    RichReprDecor: type[RichReprable]
    
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint,
                 **kwargs: Any
    ) -> None:
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
                    self.var_to_goals.set(
                        var, self.var_to_goals.get(
                            var, Set[GoalVared]()).add(goal))
        if vars:
            self.vars: tuple[Var, ...] = tuple(vars)
    
    def get_entanglement(self: Self) -> AB.Mapping[GoalVared, int]:
        """Returns a mapping of goals to their entanglement value.
        
        Entanglement is a measure of shared variables between goals.
        Computed as the product of the number of goals sharing a variable
        for goal's variables minus 1. 0 means no shared variables.
        """
        return {goal: sum((max((0, len(self.var_to_goals[var]) - 1))
                            for var in goal.vars))
                for goal in (g for g in self.goals
                             if isinstance(g, GoalVared))}
    
    def get_ctx_entanglement(self: Self, ctx: Ctx,
                             goals: Iterable[Goal] | None = None
    ) -> tuple[Ctx,
               AB.Mapping[GoalVared, int],
               AB.Mapping[Var, AB.Set[GoalVared]],
               AB.Mapping[GoalVared, AB.Set[Var]]]:
        """Contextual mapping of goals to their entanglement value.
        
        If goals are provided, only those goals are considered.  This
        is useful since heuristics may contextually modify the goals of
        a connective.
        """
        vared: list[GoalVared]
        if goals is None:
            goals = self.goals
        vared = [g for g in goals if isinstance(g, GoalVared)]
        # these may be different from self.vars after walking
        goal_to_vars: dict[GoalVared, set[Var]] = defaultdict(set)
        var_to_goals: dict[Var, set[GoalVared]] = defaultdict(set)
        for goal in vared:
            for var in goal.get_ctx_vars(ctx):
                var_to_goals[var].add(goal)
                goal_to_vars[goal].add(var)
        return (ctx,
                # {goal: sum((max((0, len(var_to_goals[var]) - 1))
                #              for var in goal_to_vars[goal]))
                #  for goal in vared},
                {goal: prod([len(var_to_goals[var])
                             for var in goal_to_vars[goal]]) - 1
                 for goal in vared},
                var_to_goals,
                goal_to_vars)

    def __call__(self: Self, ctx: Ctx) -> Stream:
        ctx, (_, constraints, goals) = HooksPipelines.run(
            ctx, type(self).hook_heuristic,
            (self, self.constraints, self.goals))
        for constraint in constraints:
            ctx = constraint.constrain(ctx)
        return self._compose_goals(ctx, goals)
    
    @classmethod
    @abstractmethod
    def _compose_goals(cls: type[Self], ctx: Ctx,
                       goals: tuple[Goal, ...]
    ) -> Stream:
        raise NotImplementedError
    
    @classmethod
    def hook_heuristic(cls: type[Self], ctx: Ctx,
        cb: HookPipelineCB[tuple[Self,
                                 tuple[Constraint, ...],
                                 tuple[Goal, ...]]]
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


# TODO: abstract generalized heuristic protocol.
# TODO: decide if heuristics should have hooks generally or not.
#    if yes, ABC can define __call__ and call __heuristic__.
class ConnectiveHeuristic[T: ConnectiveABC](
    HookPipelineCB[tuple[T, tuple[Constraint, ...], tuple[Goal, ...]]],
    CtxInstallable,
    ABC
):
    def install(self: Self, ctx: Ctx) -> Ctx:
        return Installations.install(ctx, self)


class ConjunctiveHeuristic(ConnectiveHeuristic[And]):
    def __ctx_install__(self: Self, ctx: Ctx) -> Ctx:
        return And.hook_heuristic(ctx, self)


class DisjunctiveHeuristic(ConnectiveHeuristic[Or]):
    def __ctx_install__(self: Self, ctx: Ctx) -> Ctx:
        return Or.hook_heuristic(ctx, self)


class HeurConjCardinality(ConjunctiveHeuristic):
    def __call__(self: Self, ctx: Ctx,
        data: tuple[And, tuple[Constraint, ...], tuple[Goal, ...]]
    ) -> tuple[Ctx, tuple[And,
                          tuple[Constraint, ...],
                          tuple[Goal, ...]]]:
        connective, constraints, goals = data
        varedsized, _, _, _ = discriminate_goals(goals)
        ctx, _, v2g, _ = connective.get_ctx_entanglement(
            ctx, goals)
        cardinality_constraints: list[PositiveCardinalityProduct] = []
        varsized_set = set(varedsized)
        for var, gs in v2g.items():
            cardinality_constraints.append(
                PositiveCardinalityProduct((var,), tuple(
                    g for g in gs if g in varsized_set)))
        data_procced = (
            connective, (*constraints, *cardinality_constraints), goals)
        return ctx, data_procced


class HeurConjChainVars(ConjunctiveHeuristic):
    def __call__(self: Self, ctx: Ctx,
        data: tuple[And, tuple[Constraint, ...], tuple[Goal, ...]]
    ) -> tuple[Ctx, tuple[And,
                          tuple[Constraint, ...],
                          tuple[Goal, ...]]]:
        # Order conjunction goals by their search-space size over magnitude
        # of entanglement, clustering goals by their shared variables.
        connective, constraints, goals = data
        varedsized, onlysized, onlyvared, others = discriminate_goals(goals)
        sizes = {g: g.__ctx_len__(ctx) for g in chain(varedsized, onlysized)}
        ctx, entanglement, v2g, g2v = connective.get_ctx_entanglement(
            ctx, goals)
        def order_key(goal: GoalCtxSizedVared) -> float:
            return sizes[goal] / (entanglement[goal] + 1)
        varedsized.sort(key=order_key)
        staged: set[GoalCtxSizedVared] = set()
        for i in range(len(varedsized) - 2):
            goal = varedsized[i]
            proced = varedsized[0:i+1]
            staged = staged.union(g for v in g2v[goal] for g in v2g[v]
                                  if g not in proced
                                  and isinstance(g, GoalCtxSizedVared))
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
        onlysized.sort(key=lambda g: g.__ctx_len__(ctx))
        onlyvared.sort(key=lambda g: entanglement[g], reverse=True)
        data_procced = (connective, constraints, tuple(chain(
            varedsized, onlysized, onlyvared, others)))
        # TODO: decide if broadcast or event hook needs to run or not
        return ctx, data_procced
