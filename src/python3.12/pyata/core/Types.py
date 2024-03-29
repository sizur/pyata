#!/usr/bin/env python3.12
# pyright: reportUnusedClass=false
# https://peps.python.org/pep-0695/

from __future__ import annotations
from collections.abc import Hashable, Sized
from contextlib import AbstractContextManager
from typing import (Any, Callable, ClassVar, Iterable, Iterator, Mapping,
                    Protocol, Self, TypeGuard, runtime_checkable)

from immutables import Map, MapMutation
from rich.repr import Result as rich_repr_Result
import sympy          as SY

__all__: list[str] = [

    # Core Types
    'Ctx', 'NoCtx', 'Facet', 'Var', 'Reifier', 'Arg', 'ArgStruct',
    'CtxInstallable', 'CtxConsumer', 'CtxMutation', 'CtxFunction',

    # Facet Convenience Types (ContextManager)
    'FacetBindable', 'BoundFacet',

    # Rich Repr-able Types
    'FacetRichReprable', 'BoundFacetRichReprable', 'RichReprable',
    'FacetKeyOrd', 'CtxClsRichReprable', 'CtxSelfRichReprable',
    'isCtxClsRichReprable', 'isCtxSelfRichReprable', 'isRichReprable',

    # miniKanren Core Types
    'Stream', 'Goal', 'Connective', 'Constraint', 'Relation', 'Vared',
    'GoalCtxSizedVared', 'CtxSized', 'RelationSized', 'GoalVared',
    'GoalCtxSized', 'MaybeCtxSized', 'Progressable', 'Named',

    # Hooking Types
    'HookEventCB', 'HookPipelineCB', 'HookBroadcastCB', 'HookCB',
    'BroadcastKey', 'isBroadcastKey'
]

#############################################################################
#  The Context
# -------------
#

type Ctx = Map[type[Facet[Any, Any]], Map[Any, Any]]

NoCtx: Ctx = Map[type['Facet[Any, Any]'], Map[Any, Any]]()

@runtime_checkable
class CtxConsumer[**P, R](Protocol):
    def __call__(self: Self, ctx: Ctx, *args: P.args, **kwargs: P.kwargs) -> R:
        raise NotImplementedError

@runtime_checkable
class CtxFunction[**P, *R](CtxConsumer[P, tuple[Ctx, *R]], Protocol): pass

@runtime_checkable
class CtxMutator[**P](CtxConsumer[P, Ctx], Protocol): pass

@runtime_checkable
class CtxMutation(Protocol):
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError


@runtime_checkable
class CtxInstallable(Protocol):
    """Interface for context extensions to install hooks."""
    def __ctx_install__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError

#############################################################################
#  Context Facet Types
# ---------------------
#
class Facet[K: Hashable, V: Hashable](Protocol):
    default_whole: ClassVar[Map[Any, Any]]
    default: ClassVar[Any]
    
    @classmethod
    def get_whole(cls: type[Self],
                  ctx: Map[type[Facet[Any, Any]], Map[Any, Any]]
    ) -> Map[K, V]:
        raise NotImplementedError
    
    @classmethod
    def get(cls: type[Self],
            ctx: Map[type[Facet[Any, Any]], Map[Any, Any]],
            key: K
    ) -> V:
        raise NotImplementedError
    
    @classmethod
    def set_whole(cls: type[Self],
                  ctx: Map[type[Facet[Any, Any]], Map[Any, Any]],
                  whole: Map[K, V]
    ) -> Map[type[Facet[Any, Any]], Map[Any, Any]]:
        raise NotImplementedError
    
    @classmethod
    def set(cls: type[Self],
            ctx: Map[type[Facet[Any, Any]], Map[Any, Any]],
            key: K,
            val: V
    ) -> Map[type[Facet[Any, Any]], Map[Any, Any]]:
        raise NotImplementedError
    
    @classmethod
    def update(cls: type[Self],
               ctx: Map[type[Facet[Any, Any]], Map[Any, Any]],
               updates: Mapping[K, V]
    ) -> Map[type[Facet[Any, Any]], Map[Any, Any]]:
        raise NotImplementedError
    
    @classmethod
    def mutate(cls: type[Self],
               ctx: Map[type[Facet[Any, Any]], Map[Any, Any]],
               mutator: Callable[[MapMutation[K, V]], None]
    ) -> Map[type[Facet[Any, Any]], Map[Any, Any]]:
        raise NotImplementedError


class BoundFacet[K: Hashable, V: Hashable](
    AbstractContextManager['BoundFacet[Any, Any]'],
    Protocol
):
    ctx: Ctx
    def get_whole(self: Self) -> Map[K, V]:
        raise NotImplementedError
    def set_whole(self: Self, store: Map[K, V]) -> Self:
        raise NotImplementedError
    def get(self: Self, key: K) -> V:
        raise NotImplementedError
    def set(self: Self, key: K, val: V) -> Self:
        raise NotImplementedError
    def update(self: Self, updates: Mapping[K, V]) -> Self:
        raise NotImplementedError
    def mutate(self: Self, mutator: Callable[[MapMutation[K, V]], None]
               ) -> Self:
        raise NotImplementedError


class FacetBindable[K: Hashable, V: Hashable](Protocol):
    def __new__(cls: type[Self], ctx: Ctx) -> BoundFacet[K, V]:
        raise NotImplementedError


#############################################################################
#  Rich Repr-able Types
# -----------------------
#
@runtime_checkable
class FacetKeyOrd[K: Hashable](Facet[K, Any], Protocol):
    @classmethod
    def __key_ord__(cls: type[Self], ctx: Ctx) -> Iterable[K]:
        raise NotImplementedError


@runtime_checkable
class RichReprable(Protocol):
    def __rich_repr__(self: Self) -> rich_repr_Result:
        raise NotImplementedError

def isRichReprable(obj: object) -> TypeGuard[RichReprable]:
    return hasattr(obj, '__rich_repr__')

@runtime_checkable
class CtxClsRichReprable(Protocol):
    @classmethod
    def __ctx_cls_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        raise NotImplementedError

def isCtxClsRichReprable(obj: object) -> TypeGuard[CtxClsRichReprable]:
    return hasattr(obj, '__ctx_cls_rich_repr__')

class FacetRichReprable(Facet[Any, Any], CtxClsRichReprable, Protocol): pass

@runtime_checkable
class CtxSelfRichReprable(Protocol):
    def __ctx_self_rich_repr__(self: Self, ctx: Ctx) -> tuple[Ctx, RichReprable]:
        raise NotImplementedError

def isCtxSelfRichReprable(obj: object) -> TypeGuard[CtxSelfRichReprable]:
    return hasattr(obj, '__ctx_self_rich_repr__')

class BoundFacetRichReprable(BoundFacet[Any, Any], CtxSelfRichReprable,
                             Protocol): pass



#############################################################################
#  miniKanren Core Types
# ------------------------
#
class Stream(Protocol):
    def __iter__(self: Self) -> Iterator[Ctx]:
        raise NotImplementedError

# TODO: RichReprable, CtxSelfRichReprable
@runtime_checkable
class Goal(Protocol):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        raise NotImplementedError

@runtime_checkable
class Vared(Protocol):
    vars: tuple[Var, ...]
    
    def get_ctx_vars(self: Self, ctx: Ctx) -> Iterable[Var]:
        raise NotImplementedError

@runtime_checkable
class CtxSized(Protocol):
    def __ctx_len__(self: Self, ctx: Ctx) -> int:
        raise NotImplementedError

@runtime_checkable
class MaybeCtxSized(Protocol):
    def __maybe_ctx_len__(self: Self, ctx: Ctx) -> int:
        raise NotImplementedError

@runtime_checkable
class GoalVared(Goal, Vared, Protocol): pass

@runtime_checkable
class Progressable(Protocol):
    def progress(self: Self, cur: int, tot: int) -> None:
        raise NotImplementedError

@runtime_checkable
class Named(Protocol):
    name: str

@runtime_checkable
class GoalCtxSized(Goal, CtxSized, Progressable, Protocol): pass

@runtime_checkable
class GoalCtxSizedVared(GoalCtxSized, Vared, Protocol):
    distribution: Mapping[Var, Mapping[Any, int]]

class Connective(Goal, Protocol):
    def __init__(self: Self, goal: Goal, *g_or_c: Goal | Constraint) -> None:
        raise NotImplementedError


@runtime_checkable
class Constraint(CtxSelfRichReprable, Protocol):
    def constrain(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError
    
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError


class Relation[*T, G: Goal](Protocol):
    def __call__(self: Self, *args: *T) -> G:
        raise NotImplementedError


class RelationSized[*T, G: GoalCtxSizedVared](
    Relation[*T, G], Sized, Named, Protocol
):
    def __call__(self: Self, *args: *T) -> G:
        raise NotImplementedError
    def get_facts(self: Self) -> tuple[*T]:
        raise NotImplementedError


#############################################################################
#  Hooks Types
# ---------------
#
type HookCB[T] = HookEventCB[T] | HookPipelineCB[T] | HookBroadcastCB[T]

class HookEventCB[T](Protocol):
    def __call__(self: Self, ctx: Ctx, data: T) -> Ctx:
        raise NotImplementedError


class HookPipelineCB[T](Protocol):
    def __call__(self: Self, ctx: Ctx, data: T) -> tuple[Ctx, T]:
        raise NotImplementedError


type BroadcastKey = tuple[Any, ...]

def isBroadcastKey(key: Any) -> TypeGuard[BroadcastKey]:
    return type(key) is tuple

class HookBroadcastCB[T](Protocol):
    def __call__(self: Self, ctx: Ctx, key: BroadcastKey, data: T) -> Ctx:
        raise NotImplementedError


Var = SY.Symbol

type Reifier = Callable[[Any], Any]

type Arg[T] = Var | T

type ArgStruct[*T] = Var | tuple[*T]
