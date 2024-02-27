#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc import ABC
from collections.abc import Sized
from typing import Any, Iterable, Self, cast

import numpy as np, rich, rich.repr, rich.pretty

from .Constraints import Constraints, Notin
from .Facets      import HooksBroadcasts, HookBroadcastCB, BroadcastKey, HookPipelineCB, HooksPipelines
from .Goals       import GoalABC
from .Types       import Ctx, Var, GoalCtxSizedVared, Stream, Relation
from .Unification import Unification
from .Vars        import Substitutions
from ..config     import Settings


__all__: list[str] = [
    'FactsTable'
]


type ND1 = tuple[int]
type ND2 = tuple[int, int]

DEBUG = Settings().DEBUG


class RelationABC[*T](ABC, Relation[*T]):
    name: str
    
    def __init__(self: Self, *, name: str | None = None) -> None:
        if name is not None:
            self.name = name
        else:
            try:
                self.name = self.__name__
            except AttributeError:
                try:
                    self.name = self.__class__.__name__
                except AttributeError as e:
                    raise TypeError(
                        f'Cannot infer name for {self!r}. '
                    ) from e

class FactsTable[A: np.dtype[Any], *T](RelationABC[*T], Sized):
    arr: np.ndarray[ND2, A]
    distribution: dict[int, dict[A, int]]
    # NOTE: We want to share as much stricture as possible with the produced
    #       goals, but also be able to handle facts changes, which should
    #       not affect already produced goals (since they are indemnepotent).
    arr_ver: int
    arr_ver_latest_copy: tuple[int, np.ndarray[ND2, A]] | None
    
    class FactsGoal(GoalABC, GoalCtxSizedVared):
        # NOTE: Goals are idempotent, so optimized specializations
        #       must be careful to not break this property.
        arr         : np.ndarray[ND2, A]
        args        : tuple[*T]
        free_ixs    : tuple[int, ...]
        bound_ixs   : tuple[int, ...]
        
        _short_circuit_fail: bool
        
        def __init__(self        : Self,
                     arr         : np.ndarray[ND2, A],
                     distribution: dict[int, dict[A, int]],
                     *args       : *T,
                     name        : str | None = None
        ) -> None:
            super().__init__(name=name)
            self.arr = arr
            self.args = args
            self.vars = tuple(var for var in args if isinstance(var, Var))
            self.free_ixs = tuple(i for i, var in enumerate(args)
                                  if isinstance(var, Var))
            self.bound_ixs = tuple(i for i, var in enumerate(args)
                                   if not isinstance(var, Var))
            self._stream_distrib = None
            self._short_circuit_fail = False
            for bix in self.bound_ixs:
                val: Any = args[bix]
                isin: bool = False
                try:
                    isin = val in distribution[bix]
                except TypeError:
                    pass  # val is not hashable
                if not isin:
                    self._short_circuit_fail = True
                    break
            if self._short_circuit_fail:
                self.distribution = {}
            else:
                self.distribution = cast(dict[Var, dict[A, int]],
                    # we determined args[i] is a Var, so it is safe to cast
                    {args[i]: distribution[i].copy() for i in self.free_ixs})
        
        def _filtered(self: Self, ctx: Ctx
        ) -> tuple[
            Ctx,                      # context
            np.ndarray[ND2, A],       # filtered array
            dict[Var, dict[A, int]],  # filtered distribution
            dict[Var, Notin],         # expanded notin constraints
            tuple[int, ...]           # filtered free indexes
        ] | None:
            # global CNT
            # CNT += 1
            # print('CNT', CNT)
            
            mask: np.ndarray[ND1, np.dtype[np.bool_]] = np.ones(
                self.arr.shape[0], dtype=bool)
            for bix in self.bound_ixs:
                mask &= (self.arr[:, bix] == self.args[bix])
            
            # Filtered distribution and Notin constraints
            flt_dst: dict[Var, dict[A, int]] = {}
            notins : dict[Var, Notin       ] = {}
            
            # NOTE: During goal creation, there is no context, and bound
            #       aguments are determined by how the relation was invoked.
            #       Here the goal was invoked, we have context, and unboud
            #       arguments could have subtitutions, which need to be
            #       treated like additional bound values during goal execution.
            for fix in self.free_ixs:
                var: Any = self.args[fix]
                walked_var = var
                assert isinstance(var, Var)
                
                notins[var] = notin = self._get_var_notin(ctx, var)
                
                # A constrained domain of the variable
                domain = list(notin.fd_domain_filter(ctx,
                    self.distribution[var]))
                if not domain:
                    # If the domain is empty, we short-circuit
                    return
                
                # A filtered distribution of the variable
                flt_dst[var] = {}
                for val in self.distribution[var]:
                    if val in domain:
                        flt_dst[var][val] = self.distribution[var][val]
                
                # Further constraining based on context substitutions
                ctx, val = Substitutions.walk(ctx, var)
                if not isinstance(val, Var):
                    if val not in domain:
                        return
                    notins[var] = notin.expand(
                        v for v in flt_dst[var] if v != val)
                    ctx = Constraints.evolve_var_constraint(
                        ctx, var, notin, notins[var])
                    flt_dst[var] = {val: self.distribution[var][val]}
                    mask &= (self.arr[:, fix] == val)
                else:
                    # We look-ahead if any possible values are unifiable,
                    # and if not, we mask failing facts, expand notin, and
                    # filter the distribution.
                    walked_var = val
                    notin_adds: list[A] = []
                    ctx_ahead = HooksPipelines.clear(
                        # Clear all substitution hooks for lookahead unification
                        ctx, Substitutions.hook_substitution)
                    for val_ in domain:
                        ctx_ahead_ = Unification.unify(
                            ctx_ahead, walked_var, val_)
                        if ctx_ahead_ is Unification.Failed:
                            notin_adds.append(val_)
                            del flt_dst[var][val_]
                            if not flt_dst[var]:
                                return
                            mask &= (self.arr[:, fix] != val_)
                    if notin_adds:
                        notins[var] = notin.expand(notin_adds)
                        ctx = Constraints.evolve_var_constraint(
                            ctx, walked_var, notin, notins[var])

            flt_arr: np.ndarray[ND2, A] = self.arr[mask]
            if flt_arr.shape[0] == 0:
                return
            
            # Now we need to recalculate the distribution.
            new_distrib: dict[Var, dict[A, int]] = {}
            free_ixs = tuple(i for i, arg in enumerate(self.args)
                             if isinstance(arg, Var) and  arg in flt_dst)
            for ix in free_ixs:
                var = self.args[ix]
                assert isinstance(var, Var)
                new_distrib[var] = {}
                unique, counts = np.unique(flt_arr[:, ix],
                                           return_counts=True)
                for val, count in zip(unique, counts):
                    new_distrib[var][val] = count
            
            return ctx, flt_arr, new_distrib, notins, free_ixs
        
        @staticmethod
        def _get_var_notin(ctx: Ctx, var: Var) -> Notin:
            notin: Notin
            var_notins = [c for c in Constraints
                          .get_by_type(ctx, var, Notin)
                          if len(c.vars) == 1]
            if len(var_notins) == 1:
                notin = var_notins[0]
            elif len(var_notins) < 1:
                # if there are none, we create a new one
                notin = Notin(var)
            else:
                # if there are more than one, we merge them
                notin = var_notins[0]
                for var_notin in var_notins[1:]:
                    ctx, cset = var_notin.get_cset(ctx)
                    notin = notin.expand(cset)
            return notin

        def __call__(self: Self, ctx: Ctx) -> Stream:
            if self._short_circuit_fail:
                return
            # all this effort pays in gold by cutting exponential search
            # space growth of conjunctions as early as possible
            filtered = self._filtered(ctx)
            if filtered is None:
                return
            ctx, arr, distrib, notins, free_ixs = filtered
            
            ctx, arr = HooksPipelines.run(ctx, type(self).hook_facts, arr)
            
            success_key: BroadcastKey = (
                FactsTable.FactsGoal, self.hook_factcheck_passed)
            failure_key: BroadcastKey = (
                FactsTable.FactsGoal, self.hook_factcheck_failed)
            size = arr.shape[0]
            for i, fact in enumerate(arr):
                # Enumeration of facts is equivalent to a disjunction, so
                # each fact starts from the same context (i.e. different
                # facts of an EDB are independent of each other).
                ctx2 = ctx
                broadcast_hook_data = (
                    self, fact, i, size, distrib, notins)
                for ix in free_ixs:
                    var, val = self.args[ix], fact[ix]
                    assert isinstance(var, Var)
                    ctx2 = Unification.unify(ctx2, var, val)
                    if ctx2 is Unification.Failed:
                        ctx = HooksBroadcasts.run(
                            ctx, failure_key, broadcast_hook_data)
                        break
                    # distrib[var][val] -= 1
                    # if distrib[var][val] <= 0:
                    #     # We expand the notin as soon as a val is exhausted
                    #     notin = notins[var]
                    #     notins[var] = notin.expand((val,))
                    #     # NOTE: The constraint is expanded in the context
                    #     #       of the current fact only.
                    #     ctx2 = Constraints.evolve_var_constraint(
                    #         ctx2, var, notin, notins[var])
                else:
                    ctx = HooksBroadcasts.run(
                        ctx, success_key, broadcast_hook_data)
                    yield ctx2
        
        def __len__(self: Self) -> int:
            return len(self.arr)
        
        def __ctx_len__(self: Self, ctx: Ctx) -> int:
            if self._short_circuit_fail:
                return 0
            filtered = self._filtered(ctx)
            if filtered is None:
                return 0
            _, arr, _, _, _ = filtered
            return arr.shape[0]
        
        @classmethod
        def hook_facts(cls: type[Self], ctx: Ctx,
                       cb: HookPipelineCB[np.ndarray[ND2, A]]
        ) -> Ctx:
            """Pipeline hook for post-filter pre-unification facts."""
            return HooksPipelines.hook(ctx, cls.hook_facts, cb)
                                        
        def hook_factcheck_failed(self: Self, ctx: Ctx,
            cb: HookBroadcastCB[tuple[
                Self,                     # goal
                np.ndarray[ND1, A],       # fact
                int,                      # fact index (of goal size)
                int,                      # goal size
                dict[Var, dict[A, int]],  # distribution
                dict[Var, Notin]]]        # notin constraints
        ) -> Ctx:
            broadcast_key = (FactsTable.FactsGoal, self.hook_factcheck_failed)
            return HooksBroadcasts.hook(ctx, broadcast_key, cb)
        
        def hook_factcheck_passed(self: Self, ctx: Ctx,
            cb: HookBroadcastCB[tuple[
                Self,                     # goal
                np.ndarray[ND1, A],       # fact
                int,                      # fact index (of goal size)
                int,                      # goal size
                dict[Var, dict[A, int]],  # distribution
                dict[Var, Notin]]]        # notin constraints
        ) -> Ctx:
            broadcast_key = (FactsTable.FactsGoal, self.hook_factcheck_passed)
            return HooksBroadcasts.hook(ctx, broadcast_key, cb)
        
        def __rich_repr__(self: Self) -> rich.repr.Result:
            if self.name:
                yield self.name
            yield 'vars', self.vars
            # yield from self.args

    def __init__(self: Self,
                 arr: np.ndarray[ND2, A],
                 name: str
    ) -> None:
        assert len(arr) > 0
        name = '/'.join((name, str(arr.shape[1])))
        super().__init__(name=name)
        self.arr = arr
        distrib: dict[int, dict[A, int]] = {}
        for col in range(arr.shape[1]):
            distrib[col] = {}
            unique, counts = np.unique(arr[:, col], return_counts=True)
            for val, count in zip(unique, counts):
                distrib[col][val] = count
        self.distribution = distrib
        self.arr_ver = 0
        self.arr_ver_latest_copy = None

    def __call__(self: Self, *args: *T) -> GoalCtxSizedVared:
        if self.arr_ver_latest_copy is None:
            self.arr_ver_latest_copy = (self.arr_ver, self.arr.copy())
        co_ver, co_arr = self.arr_ver_latest_copy
        if co_ver != self.arr_ver:
            self.arr_ver_latest_copy = (self.arr_ver, self.arr.copy())
            co_ver, co_arr = self.arr_ver_latest_copy
        return self.FactsGoal(co_arr, self.distribution, *args, name=self.name)

    def __len__(self: Self) -> int:
        return self.arr.shape[0]

    def __rich_repr__(self: Self) -> rich.repr.Result:
        if self.name:
            yield self.name
        yield 'cols', self.arr.shape[1]
        yield 'rows', self.arr.shape[0]

    def get_facts(self: Self) -> Iterable[np.ndarray[ND1, A]]:
        for row in self.arr:
            yield row

    @staticmethod
    def heur_facts_ord_rnd(
        ctx: Ctx, data: np.ndarray[ND2, A]
    ) -> tuple[Ctx, np.ndarray[ND2, A]]:
        return ctx, np.random.permutation(data)


# # TODO: higher order relation
# class Invoke[R: Relation[Any], *T](RelationABC[*T]):
    
#     # TODO
#     def __call__(self: Self, /, relation: R, *args: *T]) -> GoalVared:
#         ...

