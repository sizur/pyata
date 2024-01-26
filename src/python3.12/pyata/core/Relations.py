#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from collections import defaultdict
from typing import Any, Self, no_type_check

import numpy as NP

from .Goals       import GoalABC
from .Types       import Ctx, Var, GoalSizedVared, Stream, Constraint, Relation
from .Unification import Unification
from .Vars        import Substitutions


__all__: list[str] = [
    'NDArrayRel'
]

class NDArrayRel[T: NP.dtype[Any]](Relation):
    cols: int
    arr: NP.ndarray[tuple[int, int], T]
    
    class RelGoal(GoalABC, GoalSizedVared):
        vars: tuple[Var, ...]
        arr: NP.ndarray[tuple[int, int], T]
        
        def __init__(self: Self, arr: NP.ndarray[tuple[int, int], T],
                     vars: tuple[Var, ...]) -> None:
            self.vars = vars
            self.arr = arr
        
        def __call__(self: Self, ctx: Ctx) -> Stream:
            ctx, ground, free = self._discern(ctx, self.vars)
            mask = NP.ones(len(self.arr), dtype=bool)
            for i, val in ground:
                mask &= (self.arr[:, i] == val)
            filtered_arr = NP.random.permutation(self.arr[mask])
            for row in filtered_arr:
                ctx2 = ctx
                for i, var in free:
                    ctx2 = Unification.unify(ctx2, var, row[i])
                    if ctx2 is Unification.Failed:
                        break
                yield ctx2
        
        def __len__(self: Self) -> int:
            return len(self.arr)
        
        def _discern(self: Self, ctx: Ctx, vars: tuple[Var, ...]
                    ) -> tuple[Ctx,
                               list[tuple[int, T  ]],
                               list[tuple[int, Var]]]:
            ground: list[tuple[int, T  ]] = []
            free  : list[tuple[int, Var]] = []
            for i, var in enumerate(vars):
                ctx, val = Substitutions.walk(ctx, var)
                tup = (i, val)
                if isinstance(val, Var):
                    free.append(tup)
                else:
                    ground.append(tup)
            return ctx, ground, free

        
    def __init__(self: Self, arr: NP.ndarray[tuple[int, int], T]) -> None:
        assert len(arr) > 0
        self.arr = arr
        self.cols = len(arr[0])

    @no_type_check  # TODO
    def get_constraint(self: Self, *vars: Var) -> Constraint:
        assert len(vars) == self.cols
        def constraint(ctx: Ctx) -> Ctx:
            ... # TODO
        return constraint

    def __call__(self: Self, *vars: Var) -> GoalSizedVared:
        assert len(vars) == self.cols
        return self.RelGoal(self.arr, vars)
