#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc        import ABC, abstractmethod
from typing     import Any, ClassVar, Set, Self

import rich.repr   as RR
import rich.pretty as RY

from  .Types       import ( Ctx, Var, Constraint, RichReprable          #
                          , isCtxClsRichReprable, isCtxSelfRichReprable )
from  .Facets      import ( FacetABC, FacetRichReprMixin, HooksEvents   #
                          , HookEventCB                                 )
from  .Vars        import   Substitutions
from  .Unification import   Unification
from ..immutables  import   Set


__all__: list[str] = [
    'Constraints', 'ConstraintVarsABC', 'Neq', 'Distinct'
]

class Constraints(FacetABC[Var, Set[Constraint]], FacetRichReprMixin[Var]):
    default: ClassVar[Set[Constraint]] = Set()
    
    @classmethod
    def constrain(cls: type[Self], ctx: Ctx, var: Var,
        constraint: Constraint
    ) -> Ctx:
        return cls.set(ctx, var, cls.get(ctx, var).add(constraint))

    @classmethod
    def propagate(cls: type[Self], ctx: Ctx, src: Var, dst: Var
    ) -> tuple[Ctx, Set[Constraint]]:
        """Propagate constraints from `src` Vars to `dst` Var."""
        dst_cs = cls.get(ctx, dst) | cls.get(ctx, src)
        ctx = HooksEvents.run(ctx, cls.hook_propagate, (src, dst, dst_cs))
        return cls.set(ctx, dst, dst_cs), dst_cs
    
    @classmethod
    def hook_propagate(cls: type[Self], ctx: Ctx,
        cb: HookEventCB[tuple[Var, Var, Set[Constraint]]]
    ) -> Ctx:
        return HooksEvents.hook(ctx, cls.hook_propagate, cb)

    @classmethod
    def substitution_cb(
        cls: type[Self],
        ctx: Ctx,
        data: tuple[Var, Any]
    ) -> tuple[Ctx, tuple[Var, Any]]:
        var, val = data
        cs: Set[Constraint]
        if isinstance(val, Var):
            ctx, cs = cls.propagate(ctx, var, val)
        else:
            cs = cls.get(ctx, var)
        for constraint in cs:
            # NOTE: constraints may modify ctx.
            ctx = constraint(ctx)
            if ctx is Unification.Failed:
                # NOTE: This could be a pipeline to enable further
                #   extensions to elaborate on unsatisfied constraints.
                ctx = HooksEvents.run(ctx, cls.hook_constraint_unsatisfied, (var, val))
                # raise HooksShortCircuit((ctx, var, val))
                return ctx, (var, val)
        return ctx, (var, val)

    @classmethod
    def walk_condense_cb(
        cls: type[Self],
        ctx: Ctx,
        data: tuple[Any, set[Var]]
    ) -> tuple[Ctx, tuple[Any, set[Var]]]:
        val, seen = data
        if isinstance(val, Var):
            constraints: Set[Constraint] = Set()
            for var in seen:
                ctx, cs = Constraints.propagate(ctx, var, val)
                constraints = constraints.union(cs)
            for constraint in constraints:
                ctx = constraint(ctx)
                if ctx is Unification.Failed:
                    return ctx, data
        return ctx, data

    @classmethod
    def hook_constraint_unsatisfied(
        cls: type[Self],
        ctx: Ctx,
        cb: HookEventCB[tuple[Var, Any]]
    ) -> Ctx:
        """Hook for unsatisfied constraints during substitution."""
        return HooksEvents.hook(ctx, cls.hook_constraint_unsatisfied, cb)

    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: Var) -> Any:
        return {c.__ctx_self_rich_repr__(ctx)[1] for c in cls.get(ctx, key)}
    
    @classmethod
    def install(cls: type[Self], ctx: Ctx) -> Ctx:
        ctx = Substitutions.hook_substitution(ctx, cls.substitution_cb)
       # ctx = Substitutions.hook_walk_condense(ctx, cls.walk_condense_cb)
        return ctx


class ConstraintABC(ABC, Constraint): pass

class Violation(Exception): pass

class ConstraintVarsABC(ConstraintABC, ABC):
    vars: tuple[Var, ...]
    RichReprDecor: type[RichReprable]
    
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError
    
    def constrain(self: Self, ctx: Ctx) -> Ctx:
        for var in self.vars:
            ctx = Constraints.constrain(ctx, var, self)
        return ctx
    
    def __rich_repr__(self: Self) -> RR.Result:
        for var in self.vars:
            yield var
    
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class RichRepr[C: ConstraintVarsABC](RichReprable):
            def __init__(self: Self, ego: C, ctx: Ctx) -> None:
                self.ego: C   = ego
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> RR.Result:
                ctx, ego = self.ctx, self.ego
                if ego(ctx) is Unification.Failed:
                    yield Violation()
                for v in ego.vars:
                    ctx, w = Substitutions.walk(ctx, v)
                    if w == v:
                        yield cls._repr(ctx, v)
                    else:
                        yield (RY.pretty_repr(cls._repr(ctx, v)),
                               cls._repr(ctx, w))
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecor = RichRepr
    
    def __ctx_self_rich_repr__(self: Self, ctx: Ctx) -> tuple[Ctx, RichReprable]:
        return ctx, self.RichReprDecor(self, ctx)
    
    @classmethod
    def _repr(cls: type[Self], ctx: Ctx, val: Any) -> Any:
        if isCtxSelfRichReprable(val):
            return val.__ctx_self_rich_repr__(ctx)
        elif isCtxClsRichReprable(val):
            return val.__ctx_cls_rich_repr__(ctx)
        else:
            return val

class Neq(ConstraintVarsABC):
    vars: tuple[Var, Var]
    
    def __init__(self: Self, x: Var, y: Var) -> None:
        self.vars = (x, y)
    
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        ctx, lhs = Substitutions.walk(ctx, self.vars[0])
        ctx, rhs = Substitutions.walk(ctx, self.vars[1])
        if lhs == rhs:
            return Unification.Failed
        return ctx

class Distinct(ConstraintVarsABC):
    vars: tuple[Var, ...]

    def __init__(self: Self, *vars: Var) -> None:
        self.vars = vars

    def __call__(self: Self, ctx: Ctx) -> Ctx:
        walked: set[Any] = set()
        for var in self.vars:
            ctx, val = Substitutions.walk(ctx, var)
            if val in walked:
                return Unification.Failed
            walked.add(val)
        return ctx
