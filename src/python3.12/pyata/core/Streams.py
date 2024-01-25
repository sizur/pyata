#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from typing import Iterator, Self

# import immutables     as IM
import more_itertools as MI

from .Types import Ctx, Goal, Stream


__all__: list[str] = [
    'mbind', 'mconcat'
]


def mbind(stream: Stream, goal: Goal) -> Stream:
    for ctx in stream:
        yield from goal(ctx)


mconcat = MI.interleave_longest



class StreamABC(ABC, Stream):
    @abstractmethod
    def __iter__(self: Self) -> Iterator[Ctx]:
        ...

