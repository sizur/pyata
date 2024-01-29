#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc import ABC
from collections import defaultdict
from collections.abc import Sized
from typing import Any, Iterator, Self

import numpy as np, rich, rich.repr, rich.pretty

from .Goals       import GoalABC
from .Types       import Ctx, Var, Vared, CtxSized, GoalCtxSizedVared, Stream, \
    Relation
from .Unification import Unification
from .Vars        import Substitutions
from ..immutables import Map
from ..config     import Settings

__all__: list[str] = [
    'TabRel'
]


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


class TabRel[A: np.dtype[Any], *T](RelationABC[*T], Sized):
    arr: np.ndarray[tuple[int, int], A]
    
    class RelGoal(GoalABC, CtxSized, Vared):
        arr      : np.ndarray[tuple[int, int], A]
        args     : np.ndarray[tuple[int], Any]
        free_ixs : np.ndarray[tuple[int], np.dtype[np.int_]]
        bound_ixs: np.ndarray[tuple[int], np.dtype[np.int_]]
        distribution: dict[Var, dict[Any, int]]
        direction: dict[Var, dict[Any, int]] | None
        
        def __init__(self: Self, arr: np.ndarray[tuple[int, int], A],
                     *args: *T, name: str | None = None) -> None:
            super().__init__(name=name)
            self.arr = arr
            self.args = np.array(args)
            self.direction = None
            self.vars = tuple(var for var in args if isinstance(var, Var))
            self.free_ixs = np.array(list(i for i, var in enumerate(args)
                                     if isinstance(var, Var)))
            self.bound_ixs = np.array(list(i for i, var in enumerate(args)
                                      if not isinstance(var, Var)))
            distrib = np.apply_along_axis(
                lambda x: np.bincount(x), axis=0, arr=self.arr)
            self.distribution = defaultdict(dict)
            for val in np.where(np.any(0 != distrib, axis=1))[0]:
                vns: Iterator[tuple[Var, int]]
                vns = ((v,n) for v,n in zip(self.args, distrib[val],
                                            strict=True)
                      if isinstance(v, Var))
                for var, num in vns:
                    self.distribution[var][val] = num
            
            if DEBUG:
                for var, vals in self.distribution.items():
                    acc = sum(vals.values())
                    siz = len(self.arr)
                    assert acc == siz, f'{var!r} {acc} {siz}'
        
        def order_direction(self: Self, order: dict[Var, dict[Any, int]]) -> Self:
            self.directtion = order
            return self
        
        def _filtered_arr(self: Self, ctx: Ctx
                          ) -> tuple[np.ndarray[tuple[int, int], A],
                                                         list[int]]:
            bound_idx: list[tuple[int, Any]] = []
            free_idx : list[int] = []
            for ix, var in enumerate(self.args):
                if isinstance(var, Var):
                    ctx, val = Substitutions.walk(ctx, var)
                    if isinstance(val, Var):
                        free_idx.append(ix)
                    else:
                        bound_idx.append((ix, val))
                else:
                    bound_idx.append((ix, var))
            mask = np.ones(len(self.arr), dtype=bool)
            for ix, val in bound_idx:
                mask &= (self.arr[:, ix] == val)
            return self.arr[mask], free_idx
        
        def __call__(self: Self, ctx: Ctx) -> Stream:
            arr, free_idx = self._filtered_arr(ctx)
            if self.direction is None:
                filtered_arr = np.random.permutation(arr)
            else:
                ivs: list[tuple[int, Var]] = [(i,v) for i,v in enumerate(
                    self.args) if v in self.direction]
                ixs = [i for i, _ in ivs]
                num_arr = np.zeros_like(arr)
                for i, var in ivs:
                    num_arr[:, i] = self.direction[var][arr[:, i]]
                sort_ixs = np.lexsort(num_arr.T[ixs])
                filtered_arr = arr[sort_ixs]
            for row in filtered_arr:
                ctx2 = ctx
                for ix in free_idx:
                    ctx2 = Unification.unify(ctx2, self.args[ix], row[ix])
                    if ctx2 is Unification.Failed:
                        break
                else:
                    yield ctx2
        
        def __len__(self: Self) -> int:
            return len(self.arr)
        
        def __ctx_len__(self: Self, ctx: Ctx) -> int:
            arr, _ = self._filtered_arr(ctx)
            return len(arr)
        
        def __rich_repr__(self: Self) -> rich.repr.Result:
            if self.name:
                yield self.name
            yield 'params', len(self.args)
            yield 'size', len(self.arr)
            # yield from self.args

    def __init__(self: Self, arr: np.ndarray[tuple[int, int], A],
                 **kwargs: Any) -> None:
        assert len(arr) > 0
        super().__init__(**kwargs)
        self.arr = arr

    def __call__(self: Self, *args: *T) -> GoalCtxSizedVared:
        if self.name:
            return self.RelGoal(self.arr, *args, name=self.name)
        return self.RelGoal(self.arr, *args)

    def __len__(self: Self) -> int:
        return self.arr.shape[0]

    def __rich_repr__(self: Self) -> rich.repr.Result:
        if self.name:
            yield self.name
        yield 'cols', self.arr.shape[1]
        yield 'rows', self.arr.shape[0]
