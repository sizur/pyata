#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc        import ABC, abstractmethod
from typing     import Any, ClassVar, Set, Self

import rich.repr   as RR
import rich.pretty as RY

from  .Types       import Ctx, Constraint, RichReprable
from  .Facets      import FacetABC, FacetRichReprMixin
from  .Vars        import Var, Substitutions
from  .Hooks       import HooksEvents, HookEventCB
from  .Unification import Unification
from ..immutables  import Set


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
    def sub_hook(
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
    def hook_constraint_unsatisfied(
        cls: type[Self],
        ctx: Ctx,
        cb: HookEventCB[tuple[Var, Any]]
    ) -> Ctx:
        """Hook for unsatisfied constraints during substitution."""
        return HooksEvents.hook(ctx, cls.hook_constraint_unsatisfied, cb)

    @classmethod
    def _val_repr(cls: type[Self], ctx: Ctx, key: Var) -> Any:
        return {c.__ctx_rich_repr__(ctx) for c in cls.get(ctx, key)}
    
    @classmethod
    def install(cls: type[Self], ctx: Ctx) -> Ctx:
        return Substitutions.hook_sub(ctx, cls.sub_hook)


class ConstraintVarsABC(ABC, Constraint):
    vars: tuple[Var, ...]
    RichReprDecorator: type[RichReprable]
    
    @abstractmethod
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        raise NotImplementedError
    
    @abstractmethod
    def __constraint_rich_repr__(self: Self, ctx: Ctx) -> RR.Result:
        raise NotImplementedError
    
    def constrain(self: Self, ctx: Ctx) -> Ctx:
        for var in self.vars:
            ctx = Constraints.constrain(ctx, var, self)
        return ctx
    
    def __rich_repr__(self: Self) -> RR.Result:
        for var in self.vars:
            yield var
    
    def _try_rich_repr_var(self: Self, ctx: Ctx, var: Any) -> str:
        # NOTE: ASSUMPTION: `var` did Substitutions.walk already.
        richreprable: RichReprable
        try:
            richreprable = type(var).__ctx_rich_repr__(ctx)
        except AttributeError:
            try:
                richreprable = var.__ctx_rich_repr__(ctx)
            except AttributeError:
                return RY.pretty_repr(var)
        return RY.pretty_repr(richreprable)
    
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class RichRepr[C: ConstraintVarsABC](RichReprable):
            def __init__(self: Self, ego: C, ctx: Ctx) -> None:
                self.ego: C   = ego
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> RR.Result:
                yield from self.ego.__constraint_rich_repr__(self.ctx)
        RichRepr.__name__ = cls.__name__
        cls.RichReprDecorator = RichRepr
    
    def __ctx_rich_repr__(self: Self, ctx: Ctx) -> tuple[Ctx, RichReprable]:
        return ctx, self.RichReprDecorator(self, ctx)

class Neq(ConstraintVarsABC):
    vars: tuple[Var, Var]
    
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        ctx, lhs = Substitutions.walk(ctx, self.vars[0])
        ctx, rhs = Substitutions.walk(ctx, self.vars[1])
        if lhs == rhs:
            return Unification.Failed
        return ctx
    
    def __constraint_rich_repr__(self: Self, ctx: Ctx) -> RR.Result:
        ctx, lhs = Substitutions.walk(ctx, self.vars[0])
        ctx, rhs = Substitutions.walk(ctx, self.vars[1])
        violated = lhs == rhs
        lhs_repr = self._try_rich_repr_var(ctx, lhs)
        rhs_repr = self._try_rich_repr_var(ctx, rhs)
        if violated:
            yield(f"[bold red]violated:[/bold red] "
                  f"{lhs_repr} != {rhs_repr}"        )
        else:
            yield f"{lhs_repr} != {rhs_repr}"

class Distinct(ConstraintVarsABC):
    vars: tuple[Var, ...]

    def __call__(self: Self, ctx: Ctx) -> Ctx:
        walked: set[Any] = set()
        for var in self.vars:
            ctx, val = Substitutions.walk(ctx, var)
            if val in walked:
                return Unification.Failed
            walked.add(val)
        return ctx
    
    def __constraint_rich_repr__(self: Self, ctx: Ctx) -> RR.Result:
        violated: bool = False
        walked: set[Any] = set()
        valsreprs: list[tuple[Any, str]] = []
        for var in self.vars:
            ctx, val = Substitutions.walk(ctx, var)
            repr = self._try_rich_repr_var(ctx, val)
            valsreprs.append((val, repr))
            if val in walked:
                violated = True
            walked.add(val)
        if violated:
            yield(f"[bold red]violated:[/bold red] "
                  f"{', '.join([repr for _, repr in valsreprs])}")
        else:
            yield ', '.join([repr for _, repr in valsreprs])

