#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from abc        import ABC, abstractmethod
from collections.abc import Hashable
from math import prod
from typing     import Any, Callable, ClassVar, Iterable, Set, Self

import rich
import rich.repr, rich.pretty

from  .Types       import ( Ctx, GoalCtxSized, Var, Constraint, RichReprable
                          , isCtxClsRichReprable, isCtxSelfRichReprable )
from  .Facets      import ( FacetABC, FacetRichReprMixin, HooksEvents   #
                          , HookEventCB                                 )
from  .Vars        import   Substitutions
from  .Unification import   Unification
from ..immutables  import   Set


__all__: list[str] = [
    'Constraints', 'ConstraintVarsABC', 'Neq', 'Distinct', 'Notin',
    'PositiveCardinalityProduct'
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
    def mutate_var_constraint[C: Constraint](
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        old: C,
        mutator: Callable[[C], C]
    ) -> tuple[Ctx, C]:
        new: C = mutator(old)
        return (cls.set(ctx, var, cls.get(ctx, var).discard(old).add(new)),
                new)
    
    @classmethod
    def evolve_var_constraint[C: Constraint](
        cls: type[Self],
        ctx: Ctx,
        var: Var,
        old: C,
        new: C,
    ) -> Ctx:
        return cls.set(ctx, var, cls.get(ctx, var).discard(old).add(new))

    @classmethod
    def get_by_type[C: Constraint](cls: type[Self], ctx: Ctx, var: Var,
                                   typ: type[C]
    ) -> Iterable[C]:
        return (c for c in cls.get(ctx, var) if isinstance(c, typ))

    @classmethod
    def check(cls: type[Self], ctx: Ctx, var: Var) -> Ctx:
        for constraint in cls.get(ctx, var):
            ctx = constraint(ctx)
            if ctx is Unification.Failed:
                return ctx
        return ctx
    
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
    
    def __rich_repr__(self: Self) -> rich.repr.Result:
        for var in self.vars:
            yield var
    
    def __init_subclass__(cls: type[Self], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        class RichRepr[C: ConstraintVarsABC](RichReprable):
            def __init__(self: Self, ego: C, ctx: Ctx) -> None:
                self.ego: C   = ego
                self.ctx: Ctx = ctx
            def __rich_repr__(self: Self) -> rich.repr.Result:
                ctx, ego = self.ctx, self.ego
                if ego(ctx) is Unification.Failed:
                    yield Violation()
                for v in ego.vars:
                    ctx, w = Substitutions.walk(ctx, v)
                    if w == v:
                        yield cls._repr(ctx, v)
                    else:
                        yield (rich.pretty.pretty_repr(cls._repr(ctx, v)),
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


# TODO: add support for recursive cvars checking.
class Notin(ConstraintVarsABC):
    vars: tuple[Var, ...]
    subj : Var | tuple[Var, ...]
    # "c" for "collection" or "comparings"
    cvars: tuple[Var, ...]
    cvals: frozenset[Any]

    def __init__(self: Self,
                 constrain: Var | tuple[Var, ...] | Notin,
                 collection: Iterable[Any] | None = None
    ) -> None:
        if isinstance(constrain, Notin):
            assert collection is None
            self.subj = constrain.subj
            self.vars = constrain.vars
            self.cvars = constrain.cvars
            self.cvals = constrain.cvals
            return
        if collection is None:
            collection = ()
        self.cvars = tuple(var for var in collection
                        if isinstance(var, Var))
        self.cvals = frozenset(val for val in collection
                              if not isinstance(val, Var))
        # Constraints have high perf impact (both ways),
        # so we want to optimize, especially when it adds
        # low cognitive load.
        if isinstance(constrain, Var):
            self.subj = constrain
            self.vars = (constrain, *self.cvars)
        elif isinstance(constrain, tuple):  # type: ignore
            self.subj = tuple(constrain)
            self.vars = (*self.subj, *self.cvars)
            self.__call__ = self.__call_star__
        else:
            raise TypeError(
                "'constrain' argument must be Var or tuple of Vars, "
                f"not {constrain!r}")
    
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        assert isinstance(self.subj, Var)
        ctx, val = Substitutions.walk(ctx, self.subj)
        if isinstance(val, Var):
            if self.cvars:
                for var2 in self.cvars:
                    ctx, val2 = Substitutions.walk(ctx, var2)
                    if isinstance(val2, Var) and val == val2:
                        return Unification.Failed
            return ctx
        if val in self.cvals:
            return Unification.Failed
        for var2 in self.cvars:
            ctx, val2 = Substitutions.walk(ctx, var2)
            if not isinstance(val2, Var) and val2 == val:
                return Unification.Failed
        return ctx
    
    def __call_star__(self: Self, ctx: Ctx) -> Ctx:
        assert isinstance(self.subj, tuple)
        for var in self.subj:
            ctx, val = Substitutions.walk(ctx, var)
            if isinstance(val, Var):
                if self.cvars:
                    for var2 in self.cvars:
                        ctx, val2 = Substitutions.walk(ctx, var2)
                        if isinstance(val2, Var) and val == val2:
                            return Unification.Failed
                return ctx
            if val in self.cvals:
                return Unification.Failed
            for var2 in self.cvars:
                ctx, val2 = Substitutions.walk(ctx, var2)
                if not isinstance(val2, Var) and val2 == val:
                    return Unification.Failed
        return ctx

    def expand(self: Self, collection: Iterable[Any]) -> Notin:
        new = Notin(self)
        new.cvals = self.cvals | frozenset(v for v in collection
                                           if not isinstance(v, Var))
        new.cvars = (*self.cvars, *(
            var for var in collection
            if isinstance(var, Var) and var not in self.cvars))
        if new.cvars == self.cvars and new.cvals == self.cvals:
            # minimizing context changes, so garbage pressure.
            return self
        return new

    def contract(self: Self, collection: Iterable[Any]) -> Notin:
        new = Notin(self)
        new.cvals = self.cvals - frozenset(v for v in collection
                                            if not isinstance(v, Var))
        new.cvars = tuple(
            var for var in self.cvars
            if var not in collection)
        return new

    def get_cset(self: Self, ctx: Ctx) -> tuple[Ctx, set[Any]]:
        cset = set(self.cvals)
        for var in self.cvars:
            ctx, val = Substitutions.walk(ctx, var)
            cset.add(val)
        return ctx, cset

    def fd_domain_filter(self: Self, ctx: Ctx, fd_domain: Iterable[Any]
                         ) -> Iterable[Any]:
        """Finite discrete domain filter."""
        _, cset = self.get_cset(ctx)
        for val in fd_domain:
            if isinstance(val, Hashable) and val not in cset:
                yield val

    def __rich_repr__(self: Self) -> rich.repr.Result:
        if isinstance(self.subj, tuple):
            yield 'subjects', self.subj
        else:
            yield 'subject', self.subj
        yield 'objects', self.cvars + tuple(self.cvals)


class PositiveCardinalityProduct(ConstraintVarsABC):
    vars: tuple[Var         , ...]
    conj: tuple[GoalCtxSized, ...]

    def __init__(self: Self,
                 vars : tuple[Var         , ...],
                 goals: tuple[GoalCtxSized, ...]
    ) -> None:
        self.vars = vars
        self.conj = goals
    
    def __call__(self: Self, ctx: Ctx) -> Ctx:
        size = prod([g.__ctx_len__(ctx) for g in self.conj])
        if size == 0:
            return Unification.Failed
        return ctx
