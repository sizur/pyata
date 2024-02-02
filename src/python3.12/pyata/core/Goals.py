#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sized
from math import prod
from more_itertools import interleave_longest
from typing import Any, Self, cast

import rich, \
    scipy          # type: ignore
import rich.pretty, rich.repr, \
    scipy.special  # pyright: ignore[reportMissingTypeStubs]

from .Constraints import Notin
from .Facets      import HooksBroadcasts, HookBroadcastCB
from .Types       import (Var, Ctx, Goal, GoalVared, GoalCtxSized,
                          GoalCtxSizedVared, Constraint, Stream,
                          Connective, MaybeCtxSized, RichReprable,
                          CtxSelfRichReprable
                          )
from .Unification import Unification
from .Vars        import Vars


__all__: list[str] = [
    'GoalABC', 'Succeed', 'Fail', 'Eq', 'Goal'
]


mconcat = interleave_longest


def mbind(stream: Stream, goal: Goal) -> Stream:
    for ctx in stream:
        yield from goal(ctx)


class GoalABC(ABC, Goal):
    name: str | None
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
        self.name = name
    
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Stream:
        raise NotImplementedError

    def __rich_repr__(self: Self) -> rich.repr.Result:
        if hasattr(self, 'name'):
            yield self.name
        if isinstance(self, GoalVared):
            yield self.vars
    
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
    constraining_vars: tuple[Var, ...] | None
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
        self.constraining_vars = None
        
        if (isinstance(self, MaybeCtxSized)
            and any(isinstance(g, GoalCtxSized) for g in self.goals)):
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
                if ego.constraining_vars:
                    yield 'constraining_vars', ego.constraining_vars
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
    
    # TODO: all this mess doesn't belong here.  Abstract it out.
    def get_ctx_sized_comb_mtx_and_ord(self: Self, ctx: Ctx) -> tuple[
        list[list[int | None]], dict[Var, dict[Any, int]]
    ]:
        shareds: dict[
            Var, set[GoalCtxSizedVared]] = self.get_shared_vars_of_sized()
        eligible: set[GoalCtxSized] = {g for gs in shareds.values() for g in gs}
        mtx: list[list[int | None]] = []
        shared_distrib: dict[Var, dict[Any, int]] = defaultdict(
            lambda: defaultdict(int))
        for goal1 in self.goals:
            if not isinstance(goal1, GoalCtxSized):
                mtx.append([None] * len(self.goals))
                continue
            row: list[int | None] = []
            for goal2 in self.goals:
                if not isinstance(goal2, GoalCtxSized):
                    row.append(None)
                    continue
                
                if goal1 is goal2:
                    g1_size = goal1.__ctx_len__(ctx)
                    row.append(g1_size)
                    continue
                
                g2_size = goal2.__ctx_len__(ctx)
                
                if goal1 not in eligible or goal2 not in eligible:
                    row.append(g2_size)
                    continue
                
                assert isinstance(goal1, GoalCtxSizedVared)
                assert isinstance(goal2, GoalCtxSizedVared)
                # TODO: implement heuristic for multivariate dependence using
                #       Chi-squared test, scipy.stats.contingency.association,
                #       or something similar.
                # We only consider dep structure over single vars, for now.
                shared: list[Var] = [v for v in shareds
                                     if goal1 in shareds[v]
                                     and goal2 in shareds[v]]
                accs: list[int] = []
                for var in shared:
                    g1distrib = goal1.distribution[var]
                    g2distrib = goal2.distribution[var]
                    # Now we need to compute intersection of the two
                    # distributions, then the sum of all the values.
                    # This sum square is the number of ctxs that satisfy both
                    # goals.
                    acc: int = 0
                    commons: set[Any] = set(g1distrib.keys()).intersection(
                        set(g2distrib.keys()))
                    for val in commons:
                        acc += min(g1distrib[val], g2distrib[val])
                        # We also compute total distribution of shared var
                        # values, to direct goals value selection.
                        shared_distrib[
                            var][val] += g1distrib[val] + g2distrib[val]
                    accs.append(acc)
                if accs:
                    g1g2size: int = max(accs)
                    row.append(g1g2size)
                else:
                    # the two goals don't have a directly common var, so we'll
                    # just multiply their sizes.
                    row.append(g2_size)
            mtx.append(row)
        return mtx, shared_distrib
    
    def get_shared_vars_of_sized(self: Self) -> dict[Var,
                                                     set[GoalCtxSizedVared]]:
        shareds: dict[Var, set[GoalVared]] = self.get_shared_vars()
        sized: set[GoalCtxSized] = {g for g in self.goals
                                    if isinstance(g, GoalCtxSized)}
        for var, goalset in list(shareds.items()):
            shareds[var] = goalset.intersection(sized)
        return {v: cast(set[GoalCtxSizedVared], gs)
                for v, gs in sorted(list(shareds.items()),
                                    key=And._helper_sorted_key, reverse=True)}
    
    def get_shared_vars(self: Self) -> dict[Var, set[GoalVared]]:
        shareds: dict[Var, set[GoalVared]] = defaultdict(set)
        for goal in self.goals:
            if isinstance(goal, GoalVared):
                for var in goal.vars:
                    shareds[var].add(goal)
        shareds_list: list[tuple[Var, set[GoalVared]]] = list(shareds.items())
        return {var: goals for var, goals in sorted(
            shareds_list, key=And._helper_sorted_key, reverse=True)
                if len(goals) > 1}
    
    @staticmethod
    def _helper_sorted_key(tup: tuple[Var, set[GoalVared]]) -> int:
        _, goals = tup
        return len(goals)
    
    # TODO: During the new order construction, we should utilize the
    #   available information about common variables of already ordered goals.
    def ctx_heuristic_2(self: Self, ctx: Ctx,
                        mtx: list[list[int | None]] | None,
                        shared_distrib: dict[Var, dict[Any, int]] | None
    ) -> tuple[Ctx,
               int | None,
               list[list[int | None]] | None,
               dict[Var, dict[Any, int]] | None]:
        if shared_distrib:
            var_order: list[Var] = list(shared_distrib.keys())
            var_order.sort(key=lambda v: sum(shared_distrib[v].values()))
            for goal in self.goals:
                if not isinstance(goal, GoalVared):
                    continue
                g_vars = [(v, shared_distrib[v])
                        for v in var_order if v in goal.vars]
                if not g_vars:
                    continue
                try:
                    # TODO: define a protocol for this.
                    goal.order_direction(g_vars)  # type: ignore
                except AttributeError:
                    pass
        if not mtx or all(cell is None for row in mtx for cell in row):
            return ctx, None, mtx, shared_distrib
        to_concat: list[Goal] = []
        to_sort: list[tuple[int, GoalCtxSized]] = []
        rm_rows_ixs: set[int] = set()
        for i, goal in enumerate(self.goals):
            if all(mtx[i][j] is None for j in range(len(self.goals))):
                to_concat.append(goal)
                rm_rows_ixs.add(i)
            else:
                to_sort.append((i, cast(GoalCtxSized, goal)))
        # First we find the goal with the smallest size to start with.
        def sort_by_self_len(tup: tuple[int, GoalCtxSized]) -> int:
            i, _ = tup
            size = mtx[i][i]
            assert size is not None
            return size
        to_sort.sort(key=sort_by_self_len, reverse=True)
        to_and: list[Goal] = []
        i = to_sort[-1][0]
        init_cost = mtx[i][i]
        assert init_cost is not None
        cost_upper_limit: int = init_cost
        while to_sort:
            i, goal = to_sort.pop()
            to_and.append(goal)
            # Now we find the smallest conjunctive goal.
            def sort_key(tup: tuple[int, GoalCtxSized]) -> int:
                j, _ = tup
                n = mtx[i][j]
                assert n is not None
                return n
            if to_sort:
                to_sort.sort(key=sort_key, reverse=True)
                conj_cost = mtx[i][to_sort[-1][0]]
                assert conj_cost is not None
                cost_upper_limit *= int(conj_cost)
        to_and.extend(to_concat)
        assert len(to_and) == len(self.goals)
        self.goals = tuple(to_and)
        return ctx, cost_upper_limit, mtx, shared_distrib
    
    def ctx_heuristic_3(self: Self, ctx: Ctx,
                        shared_distrib: dict[Var, dict[Any, int]]
    ) -> list[Notin]:
        """Create Notin constraints for shared vars."""
        notins: list[Notin] = []
        domains: dict[Var, set[Any]] = {
            v: set(d.keys()) for v, d in shared_distrib.items()}
        antidomains: dict[Var, set[Any]] = {
            v: set() for v in shared_distrib}
        for var in antidomains:
            for goal in self.goals:
                if not isinstance(goal, GoalCtxSizedVared):
                    continue
                if var in goal.vars:
                    antidomains[var] |= set(
                        goal.distribution[var].keys()) - domains[var]
        if antidomains:
            for var, antidomain in antidomains.items():
                if antidomain:
                    notins.append(Notin(var, antidomain))
        return notins
    
    def __call__(self: Self, ctx: Ctx) -> Stream:
        for constraint in self.constraints:
            ctx = constraint.constrain(ctx)
        
        # self.ctx_heuristic(ctx)
        mtx, shared_distrib = self.get_ctx_sized_comb_mtx_and_ord(ctx)
        notins = self.ctx_heuristic_3(ctx, shared_distrib)
        for notin in notins:
            ctx = notin.constrain(ctx)
        ctx, _, mtx, _ = self.ctx_heuristic_2(ctx, mtx, shared_distrib)

        stream: Stream = self.goals[0](ctx)
        for goal in self.goals[1:]:
            stream = mbind(stream, goal)
        return stream
    
    def __maybe_ctx_len__(self: Self, ctx: Ctx) -> int:
        return prod(g.__ctx_len__(ctx)
                    for g in self.goals
                    if isinstance(g, GoalCtxSized))

    @classmethod
    def hook_heuristic(cls: type[Self], ctx: Ctx,
        cb: HookBroadcastCB[tuple[int, int, tuple[Goal, ...]]]
    ) -> Ctx:
        return HooksBroadcasts.hook(ctx, (And, cls.hook_heuristic), cb)

    # # NOTE: Currenty not used
    # def ctx_heuristic(self: Self, ctx: Ctx) -> None:
    #     sized = tuple(g for g in self.goals if isinstance(g, GoalCtxSized))
    #     nosiz = tuple(g for g in self.goals if not isinstance(g, GoalCtxSized))
    #     if not sized:
    #         return
    #     elif len(sized) == 1:
    #         self.goals = (sized[0], *nosiz)
    #     elif len(sized) == 2:
    #         sized = sorted(sized, key=lambda g: g.__ctx_len__(ctx))
    #         self.goals = (*sized, *nosiz)
    #     else:
    #         sized = sorted(sized, key=lambda g: g.__ctx_len__(ctx))
    #         pair_sized: list[tuple[int, GoalCtxSized, GoalCtxSized]] = []
    #         sizes: dict[GoalCtxSized, int] = defaultdict(int)
    #         loop_n: int = scipy.special.comb( # type: ignore # Progress-related ╮
    #             len(sized), 2, exact=True)                           #   ╭──────╯
    #         prog_key = (And, And.ctx_heuristic, self)                #   │
    #         ctx2 = HooksBroadcasts.run(ctx, prog_key,                #   │
    #                                    (None, loop_n))               #   │
    #         n: int = 0                                               #   ╰╮
    #         for i in range(len(sized) - 1):                          #   ┊:
    #             for j in range(i + 1, len(sized)):                   #   ┊:
    #                 n += 1                                           #   ╭╯
    #                 ctx2 = HooksBroadcasts.run(ctx, prog_key,        #   │
    #                                            (n, loop_n))          # ──╯
    #                 pair_size = 0
    #                 for ctx2 in sized[i](ctx):
    #                     size = sized[j].__ctx_len__(ctx2)
    #                     sizes[sized[i]] += size
    #                     sizes[sized[j]] += size
    #                     pair_size += size
    #                 rec = (pair_size, sized[i], sized[j])
    #                 pair_sized.append(rec)
    #         pair_sized.sort(key=lambda p: p[0], reverse=True)
    #         g1 = pair_sized[0][1]
    #         goals: list[GoalCtxSized] = [g1]
    #         pair_sized = [p for p in pair_sized if g1 is not p[2]]
    #         while pair_sized:
    #             rec = pair_sized.pop()
    #             # NOTE: g1 is in scope outside the loop and will contain remainder.
    #             pair_size, g1, g2 = rec
    #             goals.append(g2)
    #             pair_sized = [p for p in pair_sized
    #                           if not(g1 is p[1] or g2 is p[2])]
    #             pair_sized.sort(key=lambda p: ((0 if g2 is p[1] else 1), p[0]),
    #                             reverse=True)
    #         goals.append(g1)  # remainder
    #         assert len(goals) == len(sized)
    #         self.goals = (*goals, *nosiz)

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
    
    def __call__(self: Self, ctx: Ctx) -> Stream:
        for constraint in self.constraints:
            ctx = constraint.constrain(ctx)
        return mconcat(*(goal(ctx) for goal in self.goals))

    def __maybe_ctx_len__(self: Self, ctx: Ctx) -> int:
        return sum(g.__ctx_len__(ctx)
                   for g in self.goals
                   if isinstance(g, GoalCtxSized))


