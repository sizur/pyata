#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-


__all__: list[str] = [
    'Ctx', 'NoCtx', 'Facet', 'FacetBindable', 'BoundFacet',
    'FacetRichReprable', 'BoundFacetRichReprable', 'RichReprable',
    'FacetKeyOrd', 'Stream', 'Goal', 'Constraint', 'Solver',
    'HookEventCB', 'HookPipelineCB', 'HookBroadcastCB', 'HookCB',
    'BroadcastKey', 'isBroadcastKey', 'isCtxClsRichReprable',
    'isCtxSelfRichReprable', 'isRichReprable', 'Connective',
    'Relation', 'GoalSized', 'GoalVared', 'GoalSizedVared',
    
    'FacetABC', 'FacetRichReprMixin', 'CtxRichRepr',
    'CtxClsRichReprable', 'CtxSelfRichReprable',
    
    'HooksPipelines', 'HooksEvents', 'HooksBroadcasts', 'HooksShortCircuit',
                          
    'Metrics',
    
    'Var', 'VarTypes', 'Substitutions', 'Vars', 'TypeAssumps', 'SymAssumps',
    '__', 'CtxVarRichRepr',
    
    'Unification',
    
    'Eq', 'Fail', 'Succeed', 'GoalABC', 'Goal', 'And', 'Or',
    
    'mbind', 'mconcat',
    
    'Constraints', 'ConstraintVarsABC', 'Neq', 'Distinct',
    
    'SolverABC', 'Solver',
    
    'NDArrayRel',
]

from .Types       import ( Ctx, NoCtx, Facet, FacetBindable, BoundFacet    #
                         , FacetRichReprable, BoundFacetRichReprable       #
                         , RichReprable, FacetKeyOrd, Stream, Goal         #
                         , Constraint, HookEventCB, HookPipelineCB         #
                         , HookBroadcastCB, HookCB, BroadcastKey           #
                         , isBroadcastKey, CtxClsRichReprable              #
                         , CtxSelfRichReprable, isCtxClsRichReprable       #
                         , isCtxSelfRichReprable, isRichReprable, Var      #
                         , Connective, Relation, GoalSized, GoalVared      #
                         , GoalSizedVared                                  )
from .Facets      import ( FacetABC, FacetRichReprMixin, CtxRichRepr       #
                         , HooksPipelines, HooksEvents, HooksBroadcasts    #
                         , HooksShortCircuit                               )
from .Metrics     import   Metrics
from .Vars        import ( Var, __, Vars, VarTypes, Substitutions          #
                         , TypeAssumps, SymAssumps, CtxVarRichRepr         )
from .Unification import   Unification
from .Goals       import   Succeed, Fail, Eq, Goal, GoalABC, And, Or
from .Streams     import   mbind, mconcat
from .Constraints import   Constraints, ConstraintVarsABC, Neq, Distinct
from .Solvers     import ( SolverABC, Solver)
from .Relations   import   NDArrayRel
