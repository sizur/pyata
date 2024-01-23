#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from typing import Any, Self

from .Unification import Unification
from .Types import Ctx, Goal, Stream


__all__: list[str] = [
    'GoalABC', 'Succeed', 'Fail', 'Eq', 'Goal'
]


# TODO: Add default rich.repr for goals.
class GoalABC(ABC, Goal):
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Stream:
        ...


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
    
    def __init__(self: Self, a: Any, b: Any) -> None:
        self.a = a
        self.b = b

    def __call__(self: Self, ctx: Ctx) -> Stream:
        ctx = Unification.unify(ctx, self.a, self.b)
        if ctx is Unification.Failed:
            return
        yield ctx
