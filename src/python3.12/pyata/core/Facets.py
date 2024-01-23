#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__  import annotations
from abc         import ABC
from collections import abc as AB
from typing      import Any, Callable, ClassVar, Final, Iterable, Mapping, Self

import rich.repr   as RR
import rich.pretty as RY

from  .Types      import ( Ctx, Facet, FacetRichReprable, FacetKeyOrd #
                         , RichReprable                               )
from ..immutables import   Map, MapMutation
from ..config     import   Settings


__all__: list[str] = ['FacetABC', 'FacetRichReprMixin', 'CtxRichRepr']


DEBUG: Final[bool] = Settings().DEBUG
if DEBUG:
    from .Hooks import HooksBroadcasts


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
    
        #       ╭────────────────────────────────────────────────────────╮
    if DEBUG: # │ -- BEGIN IF DEBUG SECTION -- BEGIN IF DEBUG SECTION -- │
        #       ╰────────────────────────────────────────────────────────╯ 
        
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

        #       ╭────────────────────────────────────────────────────────╮
    else: #     │ --- ELSE IF DEBUG SECTION --- ELSE IF DEBUG SECTION -- │
        #       ╰────────────────────────────────────────────────────────╯
            
        @classmethod
        def set_whole(cls: type[Self], ctx: Ctx, whole: Map[K, V]) -> Ctx:
            """Set the whole `Facet` of a `Context`."""
            return ctx.set(cls, whole)

        @classmethod
        def set(cls: type[Self], ctx: Ctx, key: K, val: V) -> Ctx:
            """Set value in a `Facet` of a `Context`."""
            return ctx.set(cls, cls.get_whole(ctx).set(key, val))
        
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
    RichReprDecorator: type[RichReprable]
    
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
        cls.RichReprDecorator = RichRepr
    
    @classmethod
    def __ctx_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        """Rich repr of facet in Ctx."""
        # facet = cls.get_whole(ctx)
        # cached = FacetRichReprCache.get(ctx, cls)
        # if facet in cached:
        #     richrepable = cached[facet]
        #     if richrepable is not None:
        #         return ctx, richrepable

        richreprable = cls.RichReprDecorator(ctx)
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
        return key
    
    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: K) -> Any:
        return cls.get(ctx, key)


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
            ctx, richreprable = facet.__ctx_rich_repr__(ctx)
            richreprables.append(richreprable)
        self.richreprables = richreprables
        self.ctx = ctx
    
    def __rich_repr__(self: Self) -> RR.Result:
        for richreprable in self.richreprables:
            yield richreprable
    
    def __repr__(self: Self) -> str:
        return RY.pretty_repr(self)
CtxRichRepr.__name__ = 'Context'
