#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__  import annotations
from abc         import ABC, abstractmethod
from collections import abc as AB
from typing      import ( Any, Callable, ClassVar, Final, Iterable, Literal, Mapping, NoReturn #
                        , Self, cast                                        )

import rich.repr   as RR
import rich.pretty as RY

from  .Types      import ( Ctx, Facet, FacetRichReprable, FacetKeyOrd  #
                         , RichReprable, HookBroadcastCB, HookEventCB  #
                         , HookPipelineCB, BroadcastKey,  HookCB       #
                         , isCtxClsRichReprable, isCtxSelfRichReprable #
                         , CtxFunction, CtxInstallable                 )
from ..immutables import   Map, MapMutation, Cel, cons_to_iterable
from ..config     import   Settings


__all__: list[str] = [
    'FacetABC'   , 'FacetRichReprMixin', 'CtxRichRepr'   , 'HooksABC',
    'HooksEvents', 'HooksBroadcasts'   , 'HooksPipelines', 'HooksShortCircuit',
    'HooksEffectfulCBs', 'Installations', 'Hypotheticals', 'Effemore', 'Cache',
    'Installations'
]


DEBUG: Final[bool] = Settings().DEBUG


class FacetABC[K: AB.Hashable, V: AB.Hashable](
    FacetKeyOrd[K], FacetRichReprable, Facet[K, V], ABC
):
    """Facet base class.  Facets are immutable Ctx extensions."""
    default_whole: ClassVar[Map[Any, Any]] = Map[K, V]()
    default:       ClassVar[Any]
    """Default for Facet values.  Must be overridden in subclasses."""
    
    @classmethod
    def get_whole(cls: type[Self], ctx: Ctx) -> Map[K, V]:
        """Get the whole `Facet` of a `Context`."""
        return ctx.get(cls, cls.default_whole)

    @classmethod
    def get(cls: type[Self], ctx: Ctx, key: K) -> V:
        """Get a value from a `Facet` of a `Context`."""
        return ctx.get(cls, cls.default_whole).get(key, cls.default)
    
              # ╭────────────────────────────────────────────────────────╮
    if DEBUG: # │ -- BEGIN IF DEBUG SECTION -- BEGIN IF DEBUG SECTION -- │
              # ╰────────────────────────────────────────────────────────╯ 
        
        @classmethod
        def set_whole(cls: type[Self], ctx: Ctx, whole: Map[K, V]) -> Ctx:
            """Set whole facet in Ctx."""
            ctx = ctx.set(cls, whole)
            all_facet_key = (Facet, FacetABC.set_whole)
            cls_facet_key = (cls  ,      cls.set_whole)
            ctx = HooksBroadcasts.run(ctx, all_facet_key, whole)
            ctx = HooksBroadcasts.run(ctx, cls_facet_key, whole)
            return ctx

        @classmethod
        def set(cls: type[Self], ctx: Ctx, key: K, val: V) -> Ctx:
            """Set value in facet in Ctx."""
            facet = cls.get_whole(ctx)
            ctx = ctx.set(cls, facet.set(key, val))
            all_facet_key = (Facet, FacetABC.set)
            cls_facet_key = (cls  ,      cls.set)
            ctx = HooksBroadcasts.run(ctx, all_facet_key, (key, val))
            ctx = HooksBroadcasts.run(ctx, cls_facet_key, (key, val))
            return ctx
        
        @classmethod
        def delete(cls: type[Self], ctx: Ctx, key: K) -> Ctx:
            """Delete a `key` from a `Facet` of a `Context`."""
            facet = cls.get_whole(ctx)
            ctx = ctx.set(cls, facet.delete(key))
            all_facet_key = (Facet, FacetABC.delete)
            cls_facet_key = (cls  ,      cls.delete)
            ctx = HooksBroadcasts.run(ctx, all_facet_key, key)
            ctx = HooksBroadcasts.run(ctx, cls_facet_key, key)
            return ctx
        
        @classmethod
        def update(cls: type[Self], ctx: Ctx, updates: Mapping[K, V]) -> Ctx:
            """Update facet in Ctx."""
            with cls.get_whole(ctx).mutate() as mutable:
                mutable.update(updates.items())
                ctx = cls.set_whole(ctx, mutable.finish())
            all_facet_key = (Facet, FacetABC.update)
            cls_facet_key = (cls  ,      cls.update)
            ctx = HooksBroadcasts.run(ctx, all_facet_key, updates)
            ctx = HooksBroadcasts.run(ctx, cls_facet_key, updates)
            return ctx

        @classmethod
        def mutate(
            cls: type[Self],
            ctx: Ctx,
            mutator: Callable[[MapMutation[K, V]], None]
        ) -> Ctx:
            """Mutate facet in Ctx using mutator function, taking a MapMutation."""
            with cls.get_whole(ctx).mutate() as mutant:
                mutator(mutant)
                ctx = ctx.set(cls, mutant.finish())
            all_facet_key = (Facet, FacetABC.mutate)
            cls_facet_key = (cls  ,      cls.mutate)
            ctx = HooksBroadcasts.run(ctx, all_facet_key, mutator)
            ctx = HooksBroadcasts.run(ctx, cls_facet_key, mutator)
            return ctx

          #     ╭────────────────────────────────────────────────────────╮
    else: #     │ --- ELSE IF DEBUG SECTION --- ELSE IF DEBUG SECTION -- │
          #     ╰────────────────────────────────────────────────────────╯
            
        @classmethod
        def set_whole(cls: type[Self], ctx: Ctx, whole: Map[K, V]) -> Ctx:
            """Set the whole `Facet` of a `Context`."""
            return ctx.set(cls, whole)

        @classmethod
        def set(cls: type[Self], ctx: Ctx, key: K, val: V) -> Ctx:
            """Set value in a `Facet` of a `Context`."""
            return ctx.set(cls, cls.get_whole(ctx).set(key, val))
        
        @classmethod
        def delete(cls: type[Self], ctx: Ctx, key: K) -> Ctx:
            """Delete a `key` from a `Facet` of a `Context`."""
            return ctx.set(cls, cls.get_whole(ctx).delete(key))
        
        @classmethod
        def update(cls: type[Self], ctx: Ctx, updates: Mapping[K, V]) -> Ctx:
            """Update the `Facet` of a `Context`."""
            with cls.get_whole(ctx).mutate() as mutable:
                mutable.update(updates.items())
                return cls.set_whole(ctx, mutable.finish())
            return ctx

        @classmethod
        def mutate(
            cls: type[Self],
            ctx: Ctx,
            mutator: Callable[[MapMutation[K, V]], None]
        ) -> Ctx:
            """Mutate the `Facet` of a `Context` using a function, taking a mutable."""
            with cls.get_whole(ctx).mutate() as mutant:
                mutator(mutant)
                return ctx.set(cls, mutant.finish())
            return ctx
        
    #           ╭────────────────────────────────────────────────────────╮
    #           │ ---  END IF DEBUG SECTION --- END IF DEBUG SECTION --- │
    #           ╰────────────────────────────────────────────────────────╯ 

class FacetRichReprMixin[K: AB.Hashable](FacetKeyOrd[K], FacetRichReprable, ABC):
    RichReprDecor: type[RichReprable]
    
    @classmethod
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class RichRepr(RichReprable):
            def __init__(self: Self, ctx: Ctx) -> None:
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> RR.Result:
                ctx = self.ctx
                for key in cls.__key_ordered__(ctx):
                    val = cls.get(ctx, key)
                    if val != cls.default:
                        yield (RY.pretty_repr(cls._key_repr(ctx, key)),
                                cls._val_repr(ctx, key))
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecor = RichRepr
    
    @classmethod
    def __ctx_cls_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        """Rich repr of facet in Ctx."""
        # facet = cls.get_whole(ctx)
        # cached = FacetRichReprCache.get(ctx, cls)
        # if facet in cached:
        #     richrepable = cached[facet]
        #     if richrepable is not None:
        #         return ctx, richrepable

        richreprable = cls.RichReprDecor(ctx)
        # cached.set(facet, richreprable)
        # ctx = FacetRichReprCache.set(ctx, cls, cached)
        return ctx, richreprable
    
    @classmethod
    def __key_ordered__(cls: type[Self], ctx: Ctx) -> Iterable[K]:
        """Get whole facet keys in order from Ctx."""
        ret: list[K] = sorted(list(cls.get_whole(ctx).keys()), key=str)
        return ret
    
    @classmethod
    def _key_repr(cls: type[Self], ctx: Ctx, key: K) -> Any:
        if isCtxSelfRichReprable(key):
            return key.__ctx_self_rich_repr__(ctx)
        elif isCtxClsRichReprable(key):
            return key.__ctx_cls_rich_repr__(ctx)
        else:
            return key
    
    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: K) -> Any:
        val: Any = cls.get(ctx, key)
        if isCtxSelfRichReprable(val):
            return val.__ctx_self_rich_repr__(ctx)
        elif isCtxClsRichReprable(val):
            return val.__ctx_cls_rich_repr__(ctx)
        else:
            return val

class CtxRichRepr:
    """`Context` decorator for `rich.repr`."""
    ctx: Ctx
    richreprables: list[RichReprable]
    
    def __init__(self: Self,
                 ctx: Ctx,
                 ignore_facets: AB.Set[type[Facet[Any, Any]]] = frozenset()
    ) -> None:
        richreprables: list[RichReprable] = []
        # Consistent order of facet type names.
        for _, facet in sorted(((f.__name__, f) for f in ctx)):
            if (facet in ignore_facets or
                not issubclass(facet, FacetRichReprMixin) or
                facet.get_whole(ctx) == facet.default_whole):
                # no need to repr empty, ignores, or opt-outs.
                continue
            # weaving context through.
            ctx, richreprable = facet.__ctx_cls_rich_repr__(ctx)
            richreprables.append(richreprable)
        self.richreprables = richreprables
        self.ctx = ctx
    
    def __rich_repr__(self: Self) -> RR.Result:
        for richreprable in self.richreprables:
            yield richreprable
    
    def __repr__(self: Self) -> str:
        return RY.pretty_repr(self)
CtxRichRepr.__name__ = 'Ctx'


# TODO: add CtxClsRichRepr to Indirections
class Indirections(FacetABC[Callable[..., Any], Callable[..., Any]]):
    """Contextual function overrides."""
    No: ClassVar[Callable[..., Any]] = lambda: NoReturn
    default: ClassVar[Callable[..., Any]] = No
    
    @classmethod
    def invoke[**P](cls: type[Self], ctx: Ctx, fun: Callable[P, Any],
                    *args: P.args, **kwargs: P.kwargs
    ) -> Any:
        indirection = cls.get(ctx, fun)
        if indirection is cls.No:
            return fun(*args, **kwargs)
        return indirection(*args, **kwargs)


class HooksEffectfulCBs(FacetABC[HookCB[Any], bool]):
    """Facet for marking callbacks as effectful, to skip during hypotheticals."""
    default: ClassVar[bool] = False

    @classmethod
    def add(cls: type[Self], ctx: Ctx, cb: HookCB[Any]) -> Ctx:
        return cls.set(ctx, cb, True)


class HooksABC[H: HookCB[Any]](
    FacetABC[AB.Hashable, Cel[H]],
    FacetRichReprMixin[AB.Hashable],
    ABC
):
    default: ClassVar[Cel[HookCB[Any]]] = ()
    
    @classmethod
    def hook(cls: type[Self], ctx: Ctx, key: Any, cb: H,
             *, effectful: bool = False
    ) -> Ctx:
        """Hook a callback to a key in context."""
        if effectful:
            ctx = HooksEffectfulCBs.add(ctx, cb)
        return cls.set(ctx, key, (cb, cls.get(ctx, key)))
    
    @classmethod
    def hypothetical(cls: type[Self], ctx: Ctx) -> Ctx:
        return Indirections.set(ctx, cls.run_all, cls.run_pure)

    @classmethod
    @abstractmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: Any
            ) -> Ctx | tuple[Ctx, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def run_all(cls: type[Self], ctx: Ctx, key: Any, arg: Any
                ) -> Ctx | tuple[Ctx, Any]:
        raise NotImplementedError
    
    @classmethod
    @abstractmethod
    def run_pure(cls: type[Self], ctx: Ctx, key: Any, arg: Any
                 ) -> Ctx | tuple[Ctx, Any]:
        raise NotImplementedError
    
    @classmethod
    def clear(cls: type[Self], ctx: Ctx, key: Any) -> Ctx:
        """Clear all callbacks from a key in context."""
        return cls.set(ctx, key, cls.default)
    
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
        cls.RichReprDecor = RichRepr
    
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
                    val_ = val.__name__  # type: ignore
                except AttributeError:
                    val_ = val
            vals.append(val_)
        return vals


class HooksShortCircuit(Exception):
    """Exception to short-circuit hooks."""
    def __init__(self: Self, ctx: Ctx | None = None, val: Any | None = None
                 ) -> None:
        self.ctx: Ctx | None = ctx
        self.val: Any | None = val


# TODO: decide if indirections are actually necessary here or not.
class HooksEvents[T](HooksABC[HookEventCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: Any) -> Ctx:
        """Run event callbacks in context."""
        return Indirections.invoke(ctx, cls.run_all, ctx, key, arg)
    
    @classmethod
    def run_all(cls: type[Self], ctx: Ctx, key: Any, arg: Any) -> Ctx:
        cb: HookEventCB[Any]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            try:
                ctx = cb(ctx, arg)
            except HooksShortCircuit as e:
                if e.ctx is not None:
                    ctx = e.ctx
                break
        return ctx

    @classmethod
    def run_pure(cls: type[Self], ctx: Ctx, key: Any, arg: Any) -> Ctx:
        cb: HookEventCB[Any]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            if HooksEffectfulCBs.get(ctx, cb):
                continue
            try:
                ctx = cb(ctx, arg)
            except HooksShortCircuit as e:
                if e.ctx is not None:
                    ctx = e.ctx
                break
        return ctx
    
    # Override indirections to run_all, for now.
    run = run_all


class HooksBroadcasts[T](HooksABC[HookBroadcastCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: BroadcastKey, arg: T) -> Ctx:
        """Broadcast arg to key callbacks in context."""
        return Indirections.invoke(ctx, cls.run_all, ctx, key, arg)
    
    @classmethod
    def run_all(cls: type[Self], ctx: Ctx, key: BroadcastKey, arg: T) -> Ctx:
        """Broadcast arg to key callbacks in context."""
        k: Any
        for k in (key[:i] for i in range(len(key), 0, -1)):
            for bcb in cons_to_iterable(cls.get(ctx, k)):
                try:
                    ctx = bcb(ctx, key, arg)
                except HooksShortCircuit as e:
                    if e.ctx is not None:
                        ctx = e.ctx
                    break
        return ctx

    @classmethod
    def run_pure(cls: type[Self], ctx: Ctx, key: BroadcastKey, arg: T) -> Ctx:
        """Broadcast arg to key callbacks in context."""
        k: Any
        for k in (key[:i] for i in range(len(key), 0, -1)):
            for bcb in cons_to_iterable(cls.get(ctx, k)):
                if HooksEffectfulCBs.get(ctx, bcb):
                    continue
                try:
                    ctx = bcb(ctx, key, arg)
                except HooksShortCircuit as e:
                    if e.ctx is not None:
                        ctx = e.ctx
                    break
        return ctx
    
    # Override indirections to run_all, for now.
    run = run_all


class HooksPipelines[T](HooksABC[HookPipelineCB[T]]):
    @classmethod
    def run(cls: type[Self], ctx: Ctx, key: Any, arg: T) -> tuple[Ctx, T]:
        """Pipeline arg through key callbacks in context."""
        return Indirections.invoke(ctx, cls.run_all, ctx, key, arg)
    
    @classmethod
    def run_all(cls: type[Self], ctx: Ctx, key: Any, arg: T) -> tuple[Ctx, T]:
        """Pipeline arg through key callbacks in context."""
        cb: HookPipelineCB[T]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            try:
                ctx, arg = cb(ctx, arg)
            except HooksShortCircuit as e:
                if e.val is not None and isinstance(e.val, type(arg)):
                    arg = e.val
                    if e.ctx is not None:
                        ctx = e.ctx
                else:
                    raise RuntimeError(f"Invalid value: {e.val}") from e
                break
        return ctx, arg

    @classmethod
    def run_pure(cls: type[Self], ctx: Ctx, key: Any, arg: T) -> tuple[Ctx, T]:
        """Pipeline arg through key callbacks in context."""
        cb: HookPipelineCB[T]
        for cb in cons_to_iterable(cls.get(ctx, key)):
            if HooksEffectfulCBs.get(ctx, cb):
                continue
            try:
                ctx, arg = cb(ctx, arg)
            except HooksShortCircuit as e:
                if e.val is not None and isinstance(e.val, type(arg)):
                    arg = e.val
                    if e.ctx is not None:
                        ctx = e.ctx
                else:
                    raise RuntimeError(f"Invalid value: {e.val}") from e
                break
        return ctx, arg

    # Override indirections to run_all, for now.
    run = run_all


type INSTALLATIONS_T = Literal["installations"]
INSTALLATIONS: Final[INSTALLATIONS_T] = "installations"

class Installations(FacetABC[INSTALLATIONS_T, Cel[CtxInstallable]]):
    default: ClassVar[Cel[CtxInstallable]] = ()

    @classmethod
    def install(cls: type[Self], ctx: Ctx, installable: CtxInstallable) -> Ctx:
        if installable in cls.get_installations(ctx):
            raise RuntimeError(f"Already installed: {installable}")
        ctx = installable.__ctx_install__(ctx)
        return cls.set(ctx, INSTALLATIONS, (
            installable, cls.get(ctx, INSTALLATIONS)))

    @classmethod
    def get_installations(cls: type[Self], ctx: Ctx
                          ) -> Iterable[CtxInstallable]:
        return cons_to_iterable(cls.get(ctx, INSTALLATIONS))


type HYPOTHETICAL_T = Literal["hypothetical"]
HYPOTHETICAL: Final[HYPOTHETICAL_T] = "hypothetical"

class Hypotheticals(FacetABC[HYPOTHETICAL_T, bool]):
    default: ClassVar[bool] = False
    
    @classmethod
    def is_hypothetical(cls: type[Self], ctx: Ctx) -> bool:
        return cls.get(ctx, HYPOTHETICAL)

    @classmethod
    def get_hypothetical(cls: type[Self], ctx: Ctx) -> Ctx:
        """Hypothetical context, skipping effectful hooks."""
        if cls.is_hypothetical(ctx):
            return ctx
        ctx = cls.set(ctx, HYPOTHETICAL, True)
        for hooks in (HooksEvents, HooksBroadcasts, HooksPipelines):
            ctx = hooks.hypothetical(ctx)
        return ctx


class Effemore(FacetABC[AB.Hashable, int]):
    """Like a semaphore, but for contextually effectful operations."""
    default: ClassVar[int] = 1

    @classmethod
    def inc(cls: type[Self], ctx: Ctx, key: AB.Hashable) -> Ctx:
        return cls.set(ctx, key, cls.get(ctx, key) + 1)

    @classmethod
    def dec(cls: type[Self], ctx: Ctx, key: AB.Hashable) -> Ctx:
        return cls.set(ctx, key, cls.get(ctx, key) - 1)
    
    @classmethod
    def guard(cls: type[Self], ctx: Ctx, key: AB.Hashable) -> tuple[Ctx, bool]:
        if cls.get(ctx, key) > 0:
            ctx = cls.dec(ctx, key)
            return ctx, True
        return ctx, False


class Cache(FacetABC[AB.Hashable, tuple[Any, ...] | None]):
    """Contextual cache.
    
    Internally, values are wrapped in tuples to distinguish between default
    None representing key not having been cached, and a cached value of None;
    and to support context persistence.
    """
    default: ClassVar[Any] = None

    @classmethod
    def is_cached(cls: type[Self], ctx: Ctx, key: AB.Hashable) -> bool:
        return cls.get(ctx, key) is not None
    
    @classmethod
    def invoke_and_store[**P, R](cls: type[Self], ctx: Ctx,
        fun: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> tuple[Ctx, R]:
        """Invoke a function with args and cache the result."""
        ret = fun(*args, **kwargs)
        return (cls.set(ctx, (fun, args, kwargs), (ret,)), ret)
    
    @classmethod
    def cached_or_invoke[**P, R](cls: type[Self], ctx: Ctx,
        fun: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> tuple[Ctx, R]:
        """Return cached result or invoke function and cache result.
        
        Note: `CtxFunction`s should not use this interface, but instead
        `ctx_cached_or_invoke` to exclude the immutable context from the
        cache key, unless cahcing only for the original context is desired.
        """
        cached = cls.get(ctx, (fun, args, kwargs))
        if cached is not None:
            return ctx, cast(R, cached[0])
        return cls.invoke_and_store(ctx, fun, *args, **kwargs)

    @classmethod
    def ctx_invoke_and_store[**P, *R](cls: type[Self], ctx: Ctx,
                                     fun: CtxFunction[P, *R],
                                     *args: P.args, **kwargs: P.kwargs
    ) -> tuple[Ctx, *R]:
        """Invoke contextual function, exclude ctx from cache."""
        ret: tuple[Ctx, *R]
        ret = fun(ctx, *args, **kwargs)
        res: tuple[*R]
        ctx, res = ret[0], ret[1:]
        return (cls.set(ctx, (fun, args, kwargs), res), *res)
    
    @classmethod
    def ctx_cached_or_invoke[**P, *R](cls: type[Self], ctx: Ctx,
                                     fun: CtxFunction[P, *R],
                                     *args: P.args, **kwargs: P.kwargs
    ) -> tuple[Ctx, *R]:
        """Return cached result or invoke contextual function and cache result.
        
        This is required for contextual functions to be cached for derived
        contexts.  Otherwize, since the context would be part of the cache
        key, the invocation would be cached only for the original context,
        due to immutability of contexts.
        """
        cached = cls.get(ctx, (fun, args, kwargs))
        if cached is not None:
            assert isinstance(cached, tuple)
            return (ctx, *cast(tuple[*R], cached))
        return cls.ctx_invoke_and_store(
            ctx, fun,  # pyright: ignore[reportArgumentType]
            *args, **kwargs)
