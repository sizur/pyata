#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from typing import Any, Self

from rich.repr import Result as rich_repr_Result

from .Types       import Ctx, Goal, Constraint, Stream, Connective
from .Streams     import mbind, mconcat
from .Unification import Unification


__all__: list[str] = [
    'GoalABC', 'Succeed', 'Fail', 'Eq', 'Goal'
]


# TODO: Add default rich.repr for goals.
class GoalABC(ABC, Goal):
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Stream:
        raise NotImplementedError



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
    
    def __rich_repr__(self: Self) -> rich_repr_Result:
        yield self.a
        yield self.b


class ConnectiveABC(GoalABC, Connective, ABC):
    goals: tuple[Goal, ...]
    constraints: tuple[Constraint, ...]
    
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint) -> None:
        goals: list[Goal] = []
        constraints: list[Constraint] = []
        for g_c in g_or_c:
            if isinstance(g_c, Constraint):
                constraints.append(g_c)
            else:
                goals.append(g_c)
        self.constraints = tuple(constraints)
        self.goals = (goal, *goals)
        
    def __rich_repr__(self: Self) -> rich_repr_Result:
        yield self.goals
        yield self.constraints


class And(ConnectiveABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        for constraint in self.constraints:
            ctx = constraint.constrain(ctx)
        stream: Stream = self.goals[0](ctx)
        for goal in self.goals[1:]:
            stream = mbind(stream, goal)
        return stream


class Or(ConnectiveABC):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        for constraint in self.constraints:
            ctx = constraint.constrain(ctx)
        return mconcat(*(goal(ctx) for goal in self.goals))
