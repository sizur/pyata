#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from abc import ABC, abstractmethod
from collections.abc import Hashable
from typing import Any, ClassVar, Iterable, Self, cast

import rich.repr   as RR
import rich.pretty as RY

from .Types import (
    HookBroadcastCB, HookEventCB, HookPipelineCB, BroadcastKey,  HookCB,
    Ctx, RichReprable)
from .Facets import FacetABC, FacetRichReprMixin
from ..immutables import Cel, cons_to_iterable


__all__: list[str] = [
    'HooksABC', 'HooksEvents', 'HooksBroadcasts', 'HooksPipelines',
    'HooksShortCircuit'
]


class HooksABC[H: HookCB[Any]](
    FacetABC[Hashable, Cel[H]],
    FacetRichReprMixin[Hashable],
    ABC
):
    default: ClassVar[Cel[HookCB[Any]]] = ()
    
    @classmethod
    def hook(cls: type[Self], ctx: Ctx, key: Any, cb: H) -> Ctx:
        """Hook a callback to a key in context."""
        return cls.set(ctx, key, (cb, cls.get(ctx, key)))

    @classmethod
    @abstractmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: Any
            ) -> Ctx | tuple[Ctx, Any]:
        raise NotImplementedError
    
    @classmethod
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class CBsRichReprBase(RichReprable):
            def __init__(self: Self, ctx: Ctx, key: Any) -> None:
                self.ctx: Ctx = ctx
                self.key: Any = key
            def __rich_repr__(self: Self) -> RR.Result:
                yield from cls._val_repr(self.ctx, self.key)
        class RichRepr(RichReprable):
            def __init__(self: Self, ctx: Ctx) -> None:
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> RR.Result:
                key: Any
                for key in cls.__key_ordered__(self.ctx):
                    class CBsRichRepr(CBsRichReprBase): pass
                    if type(key) is tuple:
                        CBsRichRepr.__name__ = RY.pretty_repr(cls._key_repr(self.ctx, key))
                    else:
                        CBsRichRepr.__name__ = cls._key_repr(self.ctx, key)
                    yield CBsRichRepr(self.ctx, key)
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecorator = RichRepr
    
    @classmethod
    def _key_repr(cls: type[Self], ctx: Ctx, key: Any) -> Any:
        key_: Any
        if type(key) is tuple:
            return cls._key_tuple_repr_name(ctx, cast(tuple[Any, ...], key))
        try:
            key_ = key.__qualname__
        except AttributeError:
            try:
                key_ = key.__name__
            except AttributeError:
                return key
        return key_

    @classmethod
    def _key_tuple_repr_name(
        cls: type[Self],
        ctx: Ctx,
        key: tuple[Any, ...]
    ) -> tuple[Any, ...]:
        return tuple([cls._key_repr(ctx, k) for k in key])
    
    @classmethod
    def __key_ordered__(cls: type[Self], ctx: Ctx) -> Iterable[Any]:
        """Get whole facet keys in order from context.
        
        Ordering tuple keys, which are used for hierarchical broadcasts,
        are treated as structured qualified names, making them conform
        to the same alphanumeric ordering as other keys.
        """
        ret: list[Any] = sorted(list(cls.get_whole(ctx).keys()), key=(
            lambda k: ('.'.join(
                cls._key_repr(ctx, k)) if isinstance(k, tuple) else cls._key_repr(
                    ctx, k)).lower()))
        return ret
    
    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: Any) -> Any:
        vals: list[Any] = []
        val_: Any
        for val in cons_to_iterable(cls.get(ctx, key)):
            try:
                val_ = val.__qualname__.replace('<locals>.', '')
            except AttributeError:
                try:
                    val_ = val.__name__
                except AttributeError:
                    val_ = val
            vals.append(val_)
        return vals


class HooksShortCircuit[T](Exception):
    """Exception to short-circuit hooks."""
    def __init__(self: Self, ctx: Ctx | None = None, val: T | None = None
                 ) -> None:
        self.ctx: Ctx | None = ctx
        self.val: T   | None = val


class HooksEvents[T](HooksABC[HookEventCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: Any) -> Ctx:
        cb: HookEventCB[Any]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            try:
                ctx = cb(ctx, arg)
            except HooksShortCircuit[T] as e:
                if e.ctx is not None:
                    ctx = e.ctx
                break
        return ctx


class HooksBroadcasts[T](HooksABC[HookBroadcastCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: BroadcastKey, arg: T) -> Ctx:
        """Broadcast arg to key callbacks in context."""
        k: Any
        for k in (key[:i] for i in range(len(key), 0, -1)):
            for bcb in cons_to_iterable(cls.get(ctx, k)):
                try:
                    ctx = bcb(ctx, key, arg)
                except HooksShortCircuit[T] as e:
                    if e.ctx is not None:
                        ctx = e.ctx
                    break
        return ctx


class HooksPipelines[T](HooksABC[HookPipelineCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: T) -> tuple[Ctx, T]:
        """Pipeline arg through key callbacks in context."""
        cb: HookPipelineCB[T]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            try:
                ctx, arg = cb(ctx, arg)
            except HooksShortCircuit[T] as e:
                if e.val is not None and isinstance(e.val, type(arg)):
                    arg = e.val
                    if e.ctx is not None:
                        ctx = e.ctx
                else:
                    raise RuntimeError(f"Invalid value: {e.val}") from e
                break
        return ctx, arg
