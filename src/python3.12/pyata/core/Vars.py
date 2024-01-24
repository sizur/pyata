#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-


from typing import (
    Any, ClassVar, Final, Iterable, Mapping, TypedDict, Self, cast
)

import immutables     as IM
import rich.repr      as RR
import rich.pretty    as RY
import sympy          as SY

from .Types  import ( Ctx, RichReprable                           #
                    , isCtxSelfRichReprable, isCtxClsRichReprable )
from .Facets import ( FacetABC, FacetRichReprMixin, HooksEvents   #
                    , HooksPipelines, HookEventCB, HookPipelineCB )


__all__: list[str] = [
    'Var', 'VarTypes', 'Substitutions', 'Vars', 'TypeAssumps', 'SymAssumps',
    '__', 'CtxVarRichRepr'
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


Var = SY.Symbol

__: Final[Var] = Var("__")

# TODO: maybe not needed?
class CtxVarRichRepr:
    def __init__(self: Self, ctx: Ctx, var: Var) -> None:
        self.var: Var = var
        ctx, val = Substitutions.walk(ctx, var)
        if var == val or isinstance(val, Var):
            pass
        elif isCtxSelfRichReprable(val):
            ctx, val = val.__ctx_self_rich_repr__(ctx)
        elif isCtxClsRichReprable(val):
            ctx, val = val.__ctx_cls_rich_repr__(ctx)
        self.ctx = ctx
        self.val: Any = val
        
    def __rich_repr__(self: Self) -> RR.Result:
        if self.var == self.val:
            yield RY.pretty_repr(self.var)
        else:
            yield RY.pretty_repr(self.var), RY.pretty_repr(self.val)
CtxVarRichRepr.__name__ = '_'


VAR_TYP_ASSUMPS: Final[dict[type, SymAssumps]] = {
    int: SymAssumps(integer  = True, finite = True)
}


class TypeAssumps(FacetABC[type, IM.Map[str, bool]], FacetRichReprMixin[type]):
    default: ClassVar[IM.Map[str, bool]] = IM.Map[str, bool]()
    
    @classmethod
    def update_assumps(
        cls: type[Self],
        ctx: Ctx,
        defs: Mapping[type, SymAssumps]
    ) -> Ctx:
        """Update adapter for type assumptions."""
        return cls.update(
            ctx, {t: IM.Map[str, bool](
                {k: bool(b) for k, b in sa.items()}
                ) for t, sa in defs.items()})
    
    @classmethod
    def __ctx_cls_rich_repr__(cls: type[Self], ctx: Ctx) -> tuple[Ctx, RichReprable]:
        class TypeAssumpsRichRepr:
            def __init__(self: Self, cls: type[TypeAssumps], ctx: Ctx) -> None:
                self.cls: type[TypeAssumps] = cls
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> RR.Result:
                for key in cls.__key_ordered__(self.ctx):
                    class AssumpsRichRepr:
                        def __init__(self: Self, assumps: IM.Map[str, bool]) -> None:
                            self.assumps: IM.Map[str, bool] = assumps
                        def __rich_repr__(self: Self) -> RR.Result:
                            for k, v in self.assumps.items():
                                yield k, v
                    AssumpsRichRepr.__name__ = key.__name__
                    yield AssumpsRichRepr(cls.get(self.ctx, key))
        TypeAssumpsRichRepr.__name__ = cls.__name__
        return ctx, TypeAssumpsRichRepr(cls, ctx)

class VarTypes(FacetABC[Var, type | None], FacetRichReprMixin[Var]):
    default: ClassVar[type | None] = None
    
    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: Var) -> Any:
        val: type | None = cls.get(ctx, key)
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
        ctx, _ = HooksPipelines.run(ctx, cls.hook_sub, (var, val))
        return ctx

    @classmethod
    def walk(
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        _track: set[Var] | None = None
    ) -> tuple[Ctx, Any]:
        subs = cls.get_whole(ctx)
        if not (var in subs):
            return ctx, var
        sub = subs.get(var, var)
        if not (sub in subs and isinstance(sub, Var)):
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
        ctx, _ = HooksPipelines.run(ctx, cls._walk_condense, (val, tracked))
        return ctx
    
    @classmethod
    def hook_sub(
        cls: type[Self],
        ctx: Ctx,
        cb: HookPipelineCB[tuple[Var, Any]]
    ) -> Ctx:
        """Hook for substitution events for constraint propagation."""
        return HooksPipelines.hook(ctx, cls.hook_sub, cb)

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
        typ: type | None = None,
        num: int | None = None,
        /,
        **kwargs: SymAssumps
    ) -> tuple[Ctx, tuple[Var, ...]]:
        if not isinstance(typ, tuple):
            typ = (typ,)     # type: ignore
        if num is not None:
            typ = typ * num  # type: ignore
        assert not (typ == ())
        
        num = len(VarTypes.get_whole(ctx))
        new_vars: dict[Var, type | None] = {}
        for i, t in enumerate(cast(tuple[type[Any], ...], typ), 1 + num):
            new_vars[Var(f"_{i}", **TypeAssumps.get(ctx, t), **kwargs)] = t
        ctx = VarTypes.update(ctx, new_vars)
        # TODO: Decide if it should be a broadcast or a pipeline hook.
        #       Keeping it a broadcast until we have a use case for pipeline.
        ctx = HooksEvents.run(ctx, cls.hook_fresh, new_vars)
        return ctx, tuple(new_vars)

    @classmethod
    def walk_and_type_vars(
        cls: type[Self],
        ctx: Ctx,
        vars: Iterable[Var]
    ) -> tuple[Ctx, tuple[Var, ...]]:
        ret: list[Any] = []
        for var in vars:
            typ = VarTypes.get(ctx, var)
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

