#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-
from __future__ import annotations
from abc import ABC
from collections.abc import Sequence
from typing import Any, ClassVar, Final, Iterable, Iterator, Protocol, Self, cast

import numpy          as NP
import more_itertools as MI
import scipy.stats    as SS  # pyright: ignore[reportMissingTypeStubs]

from  .Types      import ( Ctx, isBroadcastKey, HookEventCB #
                         , HookBroadcastCB, BroadcastKey    )
from  .Facets     import   FacetABC, HooksEvents, HooksBroadcasts
from ..config     import   Settings


DEBUG: Final[bool] = Settings().DEBUG


###############################################################################
# A universe of a set of tuples, mapped by tuple length, and element at index.
# Variables may share universe, so enumerating the universe can remove tuples
# from the universe, which means removing all indices for that tuple, so we
# also need to have a reverse map from a tuple to its indices.
#
type Tuplen = int  # Tuple length
type Tupeli = int  # Tuple element index
type Tupkey = tuple[Tuplen, Tupeli, Any]
type Tup    = tuple[Any, ...]

class MapSetSizedTupUniverse(FacetABC[Tupkey, Tup | None]):
    default: ClassVar[Tup | None] = None
    
    class Indices[FacetABC[Tup, tuple[Tupkey] | None]]:
        default: ClassVar[tuple[Tupkey] | None] = None
    # END class Indices
    
    @classmethod
    def __init__(cls: type[Self], ctx: Ctx, tup_set: Iterable[Tup]) -> Ctx:
        for tup in tup_set:
            length = len(tup)
            for index, element in enumerate(tup):
                key: Tupkey = (length, index, element)
                el = cls.get(ctx, key)
                if el is None:
                    ctx = cls.set(ctx, key, tup)

