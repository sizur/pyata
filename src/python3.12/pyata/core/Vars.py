#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-


from abc import ABC, abstractmethod
from typing import (
    Any, Callable, ClassVar, Final, Iterable, Mapping, TypedDict, Self, cast
)

import immutables
import rich
import rich.repr, rich.pretty

from .Types  import ( Ctx, RichReprable, Var                      #
                    , CtxClsRichReprable, CtxSelfRichReprable     #
                    , Reifier                                     )
from .Facets import ( FacetABC, FacetRichReprMixin, HooksEvents   #
                    , HooksPipelines, HookEventCB, HookPipelineCB )
from ..immutables import Set, SetMutation


__all__: list[str] = [
    'Var', 'VarsReifiers', 'Substitutions', 'Vars', 'ReifiersAssumps', 'SymAssumps',
    '__', 'CtxVarRichRepr', 'VarDomains', 'DomainABC', 'FiniteDiscreteDomain'
]


# When a variable is assigned a type, it may have a set of
# `sympy` assumptions (defined here) associated with it.
class SymAssumps(TypedDict, total=False):
    """Keyword arguments for `sympy` assumptions."""
    algebraic            : bool
    commutative          : bool
    complex              : bool
    extended_negative    : bool
    extended_nonnegative : bool
    extended_nonpositive : bool
    extended_nonzero     : bool
    extended_positive    : bool
    extended_real        : bool
    finite               : bool
    hermitian            : bool
    imaginary            : bool
    infinite             : bool
    integer              : bool
    irrational           : bool
    negative             : bool
    noninteger           : bool
    nonnegative          : bool
    nonpositive          : bool
    nonzero              : bool
    positive             : bool
    prime                : bool
    rational             : bool
    real                 : bool
    transcendental       : bool
    zero                 : bool


__: Final[Var] = Var("__")

# TODO: maybe not needed?
class CtxVarRichRepr:
    def __init__(self: Self, ctx: Ctx, var: Var) -> None:
        self.ctx = ctx
        self.var: Var = var
        self.val: Any = var
        self.reify()
    
    def reify(self: Self, ctx: Ctx | None = None) -> tuple[Ctx, Any]:
        self.ctx = ctx if ctx else self.ctx
        if not isinstance(self.val, Var):
            return self.ctx, self.val
        self.ctx, self.val = Vars.walk_reify(self.ctx, self.var)
        if self.var == self.val or isinstance(self.val, Var):
            return self.ctx, self.val
        if isinstance(self.val, CtxSelfRichReprable):
            self.ctx, self.val = self.val.__ctx_self_rich_repr__(self.ctx)
        elif isinstance(self.val, CtxClsRichReprable):
            self.ctx, self.val = self.val.__ctx_cls_rich_repr__(self.ctx)
        return self.ctx, self.val
        
    def __rich_repr__(self: Self) -> rich.repr.Result:
        _, self.val = self.reify()
        if self.val == self.var:
            yield self.var
        elif isinstance(self.val, Var):
            yield (rich.pretty.pretty_repr(self.var),
                   rich.pretty.pretty_repr(self.val))
        else:
            yield rich.pretty.pretty_repr(self.var), self.val
CtxVarRichRepr.__name__ = '_'


VAR_TYP_ASSUMPS: Final[dict[type, SymAssumps]] = {
    int: SymAssumps(integer  = True, finite = True)
}


class ReifiersAssumps(FacetABC[Reifier, immutables.Map[str, bool]],
                      FacetRichReprMixin[Reifier]):
    default: ClassVar[immutables.Map[str, bool]] = immutables.Map[str, bool]()
    
    @classmethod
    def update_assumps(
        cls: type[Self],
        ctx: Ctx,
        defs: Mapping[Reifier, SymAssumps]
    ) -> Ctx:
        """Update adapter for type assumptions."""
        return cls.update(
            ctx, {t: immutables.Map[str, bool](
                {k: bool(b) for k, b in sa.items()}
                ) for t, sa in defs.items()})
    
    @classmethod
    def __ctx_cls_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        class TypeAssumpsRichRepr:
            def __init__(self: Self, cls: type[ReifiersAssumps], ctx: Ctx) -> None:
                self.cls: type[ReifiersAssumps] = cls
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> rich.repr.Result:
                for key in cls.__key_ordered__(self.ctx):
                    class AssumpsRichRepr:
                        def __init__(self: Self, assumps: immutables.Map[str, bool]) -> None:
                            self.assumps: immutables.Map[str, bool] = assumps
                        def __rich_repr__(self: Self) -> rich.repr.Result:
                            for k, v in self.assumps.items():
                                yield k, v
                    AssumpsRichRepr.__name__ = key.__name__
                    yield AssumpsRichRepr(cls.get(self.ctx, key))
        TypeAssumpsRichRepr.__name__ = cls.__name__
        return ctx, TypeAssumpsRichRepr(cls, ctx)

class VarsReifiers(FacetABC[Var, Reifier | None],
                   FacetRichReprMixin[Var]):
    default: ClassVar[Reifier | None] = None
    
    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: Var) -> Any:
        val: Reifier | None = cls.get(ctx, key)
        try:
            return val.__name__
        except AttributeError:
            return val



class Substitutions(FacetABC[Var, Any], FacetRichReprMixin[Var]):
    default: ClassVar[Any] = None
    
    @classmethod
    def sub(cls: type[Self], ctx: Ctx, var: Var, val: Any) -> Ctx:
        ctx = cls.set(ctx, var, val)
        # Constraints are checked after substitution, and may fail unification.
        ctx, _ = HooksPipelines.run(ctx, cls.hook_substitution, (var, val))
        return ctx

    @classmethod
    def walk(
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        _track: set[Var] | None = None
    ) -> tuple[Ctx, Any]:
        subs = cls.get_whole(ctx)
        if not (isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            var, Var) and var in subs
        ):
            return ctx, var
        sub = subs.get(var, var)
        if not (isinstance(sub, Var) and sub in subs):
            return ctx, sub
        track = _track if _track else {var}
        track.add(sub)
        ctx, sub = cls.walk(ctx, sub, track)
        if not _track and sub not in track:
            # Recursion is done AND condensing is possible.
            ctx, val = HooksPipelines.run(
                ctx, cls.hook_walk_condensible, (var, sub, track))
            _, sub, _ = val
        return ctx, sub
    
    @classmethod
    def _walk_condense(
        cls: type[Self],
        ctx: Ctx,
        val: Any,
        tracked: set[Var]
    ) -> Ctx:
        ctx = cls.update(ctx, {var: val for var in tracked})
        # Giving more constraint propagation opportunities.
        ctx, _ = HooksPipelines.run(ctx, cls.hook_walk_condense, (val, tracked))
        return ctx
    
    @classmethod
    def hook_walk_condense(
        cls: type[Self],
        ctx: Ctx,
        cb: HookPipelineCB[tuple[Any, set[Var]]]
    ) -> Ctx:
        return HooksPipelines.hook(ctx, cls.hook_walk_condense, cb)
    
    @classmethod
    def hook_substitution(
        cls: type[Self],
        ctx: Ctx,
        cb: HookPipelineCB[tuple[Var, Any]]
    ) -> Ctx:
        """Hook for substitution events for constraint propagation."""
        return HooksPipelines.hook(ctx, cls.hook_substitution, cb)

    @classmethod
    def hook_walk_condensible(
        cls: type[Self],
        ctx: Ctx,
        cb: HookPipelineCB[tuple[Var, Any, set[Var]]]
    ) -> Ctx:
        """Hook for condensible walk events as controls for condensing.
        
        Using metric's based heuristics, we can decide dynamically what size
        of tracked variables set should trigger condensing:
        
            def cb(ctx, var, val, tracked):
                # Use Metrics.  This is just an example.
                if len(tracked) > 10:
                    ctx = Substitutions._walk_condense(ctx, val, tracked)
                return ctx, var, val, tracked
            ctx = Substitutions.hook_walk_condensible(ctx, cb)
        """
        return HooksPipelines.hook(ctx, cls.hook_walk_condensible, cb)

class Vars:
    @classmethod
    def fresh(
        cls: type[Self],
        ctx: Ctx,
        reifier: Reifier | tuple[Reifier, ...] | None = None,
        num: int | None = None,
        /,
        **kwargs: SymAssumps
    ) -> tuple[Ctx, tuple[Var, ...]]:
        if not isinstance(reifier, tuple):
            reifier = (reifier,)     # type: ignore
        if num is not None:
            reifier = reifier * num  # type: ignore
        assert not (reifier == ())
        
        num = len(VarsReifiers.get_whole(ctx))
        new_vars: dict[Var, Reifier | None] = {}
        for i, t in enumerate(cast(tuple[Reifier, ...], reifier), 1 + num):
            new_vars[Var(f"_{i}", **ReifiersAssumps.get(ctx, t), **kwargs)] = t
        ctx = VarsReifiers.update(ctx, new_vars)
        # TODO: Decide if it should be a broadcast or a pipeline hook.
        #       Keeping it a broadcast until we have a use case for pipeline.
        ctx = HooksEvents.run(ctx, cls.hook_fresh, new_vars)
        return ctx, tuple(new_vars)

    @classmethod
    def walk_reify(
        cls: type[Self],
        ctx: Ctx,
        var: Var
    ) -> tuple[Ctx, Any]:
        ctx, val = Substitutions.walk(ctx, var)
        if isinstance(val, Var):
            return ctx, val
        typ = VarsReifiers.get(ctx, var)
        if typ is None:
            return ctx, val
        return ctx, typ(val)

    @classmethod
    def contextualize(
        cls: type[Self],
        ctx: Ctx,
        reifier: Reifier,
        *vars: Var
    ) -> tuple[Ctx, tuple[Var, ...]]:
        vartyps = VarsReifiers.get_whole(ctx)
        cconflict: list[Var] = []
        for var in vars:
            if var not in vartyps:
                ctx = VarsReifiers.set(ctx, var, reifier)
            else:
                cconflict.append(var)
        return ctx, tuple(cconflict)
    
    @classmethod
    def walk_reify_vars(
        cls: type[Self],
        ctx: Ctx,
        vars: Iterable[Var]
    ) -> tuple[Ctx, tuple[Any, ...]]:
        ret: list[Any] = []
        for var in vars:
            typ = VarsReifiers.get(ctx, var)
            ctx, var = Substitutions.walk(ctx, var)
            if typ is not None and not isinstance(var, Var):
                var = typ(var)
            ret.append(var)
        return ctx, tuple(ret)
        
    @classmethod
    def hook_fresh(
        cls: type[Self],
        ctx: Ctx,
        cb: HookEventCB[Mapping[Var, type | None]]
    ) -> Ctx:
        return HooksEvents.hook(ctx, cls.hook_fresh, cb)


class DomainABC(ABC):
    @abstractmethod
    def expand(self: Self, vals: Iterable[Any]) -> Self:
        raise NotImplementedError
    
    @abstractmethod
    def contract(self: Self, vals: Iterable[Any]) -> Self:
        raise NotImplementedError


class FiniteDiscreteDomain[T](Set[T], DomainABC):
    def expand(self: Self, vals: Iterable[T]) -> Self:
        return self.union(vals)
    
    def contract(self: Self, vals: Iterable[T]) -> Self:
        def mutator(s: SetMutation[T]) -> None:
            for val in vals:
                s.remove(val)
        return self.mutate(mutator)


# TODO: Create a protocol for domains
class VarDomains(FacetABC[Var, DomainABC | None], FacetRichReprMixin[Var]):
    default: ClassVar[DomainABC | None] = None

    @classmethod
    def expand(
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        vals: DomainABC
    ) -> Ctx:
        domain: DomainABC | None = cls.get(ctx, var)
        if domain is None:
            return cls.set(ctx, var, vals)
        else:
            return cls.set(ctx, var, domain.expand(vals))
    
    @classmethod
    def contract(
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        vals: DomainABC
    ) -> Ctx:
        domain: DomainABC | None = cls.get(ctx, var)
        if domain is None:
            return cls.set(ctx, var, vals)
        else:
            return cls.set(ctx, var, domain.contract(vals))

    @classmethod
    def is_existent(
        cls: type[Self],
        ctx: Ctx,
        var: Var
    ) -> bool:
        return cls.get(ctx, var) is not None
