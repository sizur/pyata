#!/usr/bin/env python3.12
# pyright: reportUnusedClass=false
# https://peps.python.org/pep-0695/

from __future__ import annotations
from collections.abc import Hashable
from contextlib import AbstractContextManager
from typing import (Any, Callable, ClassVar, Iterable, Iterator, Mapping,
                    Protocol, Self, TypeGuard)

from immutables import Map, MapMutation
from rich.repr import Result as rich_repr_Result

__all__: list[str] = [

    # Core Types
    'Ctx', 'Facet',

    # Facet Convenience Types (ContextManager)
    'FacetBindable', 'BoundFacet',

    # Rich Repr-able Types
    'FacetRichReprable', 'BoundFacetRichReprable', 'RichReprable',
    'FacetKeyOrd',

    # miniKanren Core Types
    'Stream', 'Goal', 'Constraint', 'Solver',

    # Hooking Types
    'HookEventCB', 'HookPipelineCB', 'HookBroadcastCB', 'HookCB',
    'BroadcastKey', 'isBroadcastKey'
]

#############################################################################
#  Data Structure Types
# ----------------------
#

type Ctx = Map[type[Facet[Any, Any]], Map[Any, Any]]


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
    def __new__(cls: type[Self], ctx: Ctx) -> 'BoundFacet[K, V]':
        raise NotImplementedError


#############################################################################
#  Rich Repr-able Types
# -----------------------
#
class FacetKeyOrd[K: Hashable](Facet[K, Any], Protocol):
    @classmethod
    def __key_ord__(cls: type[Self], ctx: Ctx) -> Iterable[K]:
        raise NotImplementedError


class RichReprable(Protocol):
    def __rich_repr__(self: Self) -> rich_repr_Result:
        raise NotImplementedError

class CtxClsRichReprable(Protocol):
    @classmethod
    def __ctx_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        raise NotImplementedError

class FacetRichReprable(Facet[Any, Any], CtxClsRichReprable, Protocol): pass

class CtxSelfRichReprable(Protocol):
    def __ctx_rich_repr__(self: Self, ctx: Ctx) -> tuple[Ctx, RichReprable]:
        raise NotImplementedError

class BoundFacetRichReprable(BoundFacet[Any, Any], CtxSelfRichReprable,
                             Protocol): pass


#############################################################################
#  miniKanren Core Types
# ------------------------
#
class Stream(Protocol):
    def __iter__(self: Self) -> Iterator[Ctx]:
        raise NotImplementedError


class Goal(RichReprable, CtxSelfRichReprable, Protocol):
    def __call__(self: Self, ctx: Ctx) -> Stream:
        raise NotImplementedError


class Constraint(CtxSelfRichReprable, Protocol):
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError


class Solver[*T](Protocol):
    def __call__(self: Self, ctxt: Ctx | None = None) -> Iterable[tuple[*T]]:
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
