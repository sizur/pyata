#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from typing import Any, Iterator, Self

from  .Types      import Ctx, Facet, Var
from  .Facets     import HooksPipelines, HookPipelineCB
from  .Vars       import __, Substitutions
from ..immutables import Map


__all__: list[str] = ['Unification', 'UnificationIterables']


class Unification:
    Failed: Ctx = Map[type[Facet[Any, Any]], Map[Any, Any]]()
    
    @classmethod
    def unify(cls: type[Self], ctx: Ctx, x: Any, y: Any) -> Ctx:
        """Unifies x and y, updating the substitution chain and returning a new state."""
        ctx, x = Substitutions.walk(ctx, x)
        ctx, y = Substitutions.walk(ctx, y)
        if x == y or x is __ or y is __:
            return ctx  # already unified
        if isinstance(x, Var):
            # NOTE: Substitutions.sub HooksPipelines may fail unification.
            return Substitutions.sub(ctx, x, y)
        if isinstance(y, Var):
            # NOTE: Substitutions.sub HooksPipelines may fail unification.
            return Substitutions.sub(ctx, y, x)
        # Trigger unification extensions pipeline.
        ctx, pair = HooksPipelines.run(ctx, cls.hook_unify, (x, y))
        x, y = pair
        if not ctx or x == y:
            return ctx                 # Hooks.pipeline has handled unification.
        return cls.Failed              # Unification failed: unhandled.
    
    @classmethod
    def hook_unify(cls: type[Self], ctx: Ctx,
        cb: HookPipelineCB[tuple[Any, Any]]
    ) -> Ctx:
        return HooksPipelines.hook(ctx, cls.hook_unify, cb)

class UnificationIterables:
    """Unification extension for iterables.
    
    Unifies iterables element-wise, iteratively.  Supports ending with `...`,
    which is prefix matching, and is enough for `Iterable` equivalents of
    difference lists and DCGs.
    """
    @classmethod
    def unify_hook(cls: type[Self], ctx: Ctx, data: tuple[Any, Any]
                   ) -> tuple[Ctx, tuple[Any, Any]]:
        x, y = data
        if not ctx or x == y:
            # Was already handled by another hook in pipeline.
            return ctx, (x, y)
        x_itr: Iterator[Any]
        y_itr: Iterator[Any]
        x_i: Any
        y_i: Any
        x_empty: bool = False
        y_empty: bool = False
        try:                          # Try unify iterators iteratively.
            x_itr = iter(x)
            y_itr = iter(y)
        except TypeError:
            return ctx, (x, y)  # Either one or both not iterable: don't handle.
        while True:
            try:
                x_i = next(x_itr)     # pyright: ignore[reportUnboundVariable]
            except StopIteration:
                x_empty = True
            try:
                y_i = next(y_itr)     # pyright: ignore[reportUnboundVariable]
            except StopIteration:
                y_empty = True
            if x_empty and y_empty:
                return ctx, ((), ())    # Unification succeeded: both empty.
            if x_empty or y_empty:
                return Unification.Failed, (x, y) # One empty, the other not.
            ctx, x_i = Substitutions.walk(ctx, x_i)  # pyright: ignore[reportPossiblyUnboundVariable]
            ctx, y_i = Substitutions.walk(ctx, y_i)  # pyright: ignore[reportPossiblyUnboundVariable]
            if x_i is ...:
                try:
                    x_j = next(x_itr) # pyright: ignore[reportUnusedVariable]
                except StopIteration:
                    # whatever the other iterable has remaining, ending x
                    # with ... will unify with it.
                    return ctx, ((), ())  # Unification succeeded: ... ends x.
                # TODO: FIXME: extend to handle ... better
                raise NotImplementedError("TODO: FIXME: extend to handle other cases.")
            if y_i is ...:
                try:
                    y_j = next(y_itr) # pyright: ignore[reportUnusedVariable]
                except StopIteration:
                    # whatever the other iterable has remaining, ending y
                    # with ... will unify with it.
                    return ctx, ((), ())  # Unification succeeded: ... ends y.
                # TODO: FIXME: extend to handle ... better
                raise NotImplementedError("TODO: FIXME: extend to handle other cases.")
            ctx = Unification.unify(ctx, x_i, y_i)
            if not ctx:
                return Unification.Failed, (x, y) # Elements not unifiable.
        assert_never(...)             # Unreachable.
