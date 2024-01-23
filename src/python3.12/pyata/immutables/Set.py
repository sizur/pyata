#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC
from collections import abc as AB
from typing import Any, Callable, Hashable, Iterable, Iterator, Self, Sized, cast

import immutables
from rich import repr

__all__ = ['Set']

class SetABC[
    V: Hashable,
    T: immutables.Map[Any, None] | immutables.MapMutation[Any, None]
](ABC, AB.Set[V]):
    """Abstract base class for HAMT sets implementing common methods."""
    __slots__ = ('impl')
    impl: T

    def __hash__(self: Self) -> int:
        return hash(self.impl)
    
    def __contains__(self: Self, value: V) -> bool:
        return value in self.impl
    
    def __iter__(self: Self) -> Iterator[V]:
        return iter(self.impl)
    
    def __len__(self: Self) -> int:
        return len(self.impl)
    
    def __repr__(self: Self) -> str:
        return f'{type(self).__name__}({set(self.impl)})'
    
    def __rich_repr__(self: Self) -> repr.Result:
        yield set(self.impl)
    
    def __str__(self: Self) -> str:
        return f'{set(self.impl)}'
    
    # TODO: other methods can be optimized too, if need be.
    def __eq__(self: Self, other: Any) -> bool:
        if type(self) == type(other):
            return self.impl == other.impl
        if isinstance(other, Sized) and len(self.impl) != len(other):
                return False
        if isinstance(other, (set, frozenset, dict)):
            # lookups in sets are O(1), so this is faster than
            return all(item in other for item in iter(self.impl))
        try:
            itr: Iterator[Any] = iter(cast(Iterable[Any], other))
        except TypeError:
            return False
        else:
            impl = self.impl
            return all(item in impl for item in itr)

    def __ne__(self: Self, other: Any) -> bool:
        return not self.__eq__(other)

class Set[T: Hashable](SetABC[T, immutables.Map[T, None]]):
    """
    `frozenset` behavior with HAMT implementation.
    
    Much lighter mutations than `frozenset` on large sets.
    """
    __slots__ = ()
    
    def __init__(self: Self, set: set[T] | immutables.Map[T, None] = immutables.Map()) -> None:
        if isinstance(set, Set):
            self.impl = cast(Set[T], set).impl
        elif isinstance(set, immutables.Map):
            self.impl = set
        else:
            self.impl = immutables.Map({v: None for v in set})
    
    def add(self: Self, value: T) -> Self:
        return type(self)(self.impl.set(value, None))
    
    def discard(self: Self, value: T) -> Self:
        return type(self)(self.impl.delete(value))
    
    def mutate(self: Self, mutator: 'Callable[[SetMutation[T]], None]') -> Self:
        with self.impl.mutate() as mutable:
            mut = SetMutation(mutable)
            mutator(mut)
            # not providing finish() in SetMutation is not a mistake
            return type(self)(mut.impl.finish())
        return self

    def __or__(self: Self, other: AB.Set[Any]) -> Self:
        impl = self.impl
        if not other:
            return self
        if isinstance(other, type(self)):
            if impl == other.impl:
                return self
            if len(impl) < len(other.impl):
                return type(self)(other.impl.update(impl))
            else:
                return type(self)(impl.update(other.impl))
        with impl.mutate() as mutable:
            for item in other:
                if item not in impl:
                    mutable[item] = None
            return type(self)(mutable.finish())
        raise RuntimeError("BUGS BUGS BUGS!!!")
    
    def union(self: Self, *others: AB.Set[Any]) -> Self:
        for other in others:
            self = self | other
        return self

class SetMutation[T: Hashable](AB.MutableSet[T], SetABC[T, immutables.MapMutation[T, None]]):
    __slots__ = ()
    
    def __init__(self: Self, mutable: immutables.MapMutation[T, None]) -> None:
        self.impl = mutable

    def add(self: Self, value: T) -> None:
        self.impl[value] = None
    
    def discard(self: Self, value: T) -> None:
        del self.impl[value]
