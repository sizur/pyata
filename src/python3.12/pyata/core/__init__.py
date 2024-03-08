#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-


__all__: list[str] = [
    'Ctx', 'NoCtx', 'Facet', 'FacetBindable', 'BoundFacet',
    'FacetRichReprable', 'BoundFacetRichReprable', 'RichReprable',
    'FacetKeyOrd', 'Stream', 'Goal', 'Constraint', 'Solver',
    'HookEventCB', 'HookPipelineCB', 'HookBroadcastCB', 'HookCB',
    'BroadcastKey', 'isBroadcastKey', 'isCtxClsRichReprable',
    'isCtxSelfRichReprable', 'isRichReprable', 'Connective',
    'Vared', 'Relation', 'GoalCtxSizedVared', 'CtxSized',
    'RelationSized', 'GoalCtxSized', 'GoalVared', 'MaybeCtxSized',
    'Reifier', 'Progressable', 'Named', 'Arg', 'CtxInstallable',
    'CtxConsumer', 'CtxFunction', 'CtxMutation',
    
    'FacetABC', 'FacetRichReprMixin', 'CtxRichRepr',
    'CtxClsRichReprable', 'CtxSelfRichReprable',
    
    'HooksPipelines', 'HooksEvents', 'HooksBroadcasts', 'HooksShortCircuit',
    'HooksEffectfulCBs', 'Hypotheticals', 'Effemore', 'Cache', 'Installations',

    'Metrics',
    
    'Var', 'VarsReifiers', 'Substitutions', 'Vars', 'ReifiersAssumps', 'SymAssumps',
    '__', 'CtxVarRichRepr', 'VarDomains', 'DomainABC', 'FiniteDiscreteDomain',
    
    'Unification', 'UnificationIterables', 'UnificationIterablesTypeGuard',
    
    'Eq', 'Fail', 'Succeed', 'GoalABC', 'Goal', 'And', 'Or',
    
    'HeurConjChainVars', 'HeurConjCardinality', 'HeurConjRelevance',
    'HeurFactsOrdRnd',
    'ConjunctiveHeuristic', 'DisjunctiveHeuristic',
    'discern_goals', 'discriminate_goals',
    
    'Constraints', 'ConstraintVarsABC', 'Neq', 'Distinct', 'Notin',
    'PositiveCardinalityProduct',
    
    'SolverABC', 'Solver',
    
    'FactsTable', 'FreshRel',
    
    'uint8', 'uint8_not', 'uint8_add', 'uint8_diff',
]

from .Types       import ( Ctx, NoCtx, Facet, FacetBindable, BoundFacet    #
                         , FacetRichReprable, BoundFacetRichReprable       #
                         , RichReprable, FacetKeyOrd, Stream, Goal         #
                         , Constraint, HookEventCB, HookPipelineCB         #
                         , HookBroadcastCB, HookCB, BroadcastKey           #
                         , isBroadcastKey, CtxClsRichReprable              #
                         , CtxSelfRichReprable, isCtxClsRichReprable       #
                         , isCtxSelfRichReprable, isRichReprable, Var      #
                         , Connective, Relation, Vared, GoalCtxSizedVared  #
                         , CtxSized, RelationSized, GoalCtxSized, GoalVared
                         , MaybeCtxSized, Reifier, Progressable, Named     #
                         , Arg, CtxInstallable, CtxConsumer, CtxFunction   #
                         , CtxMutation                                     )
from .Facets      import ( FacetABC, FacetRichReprMixin, CtxRichRepr       #
                         , HooksPipelines, HooksEvents, HooksBroadcasts    #
                         , HooksShortCircuit, Hypotheticals                #
                         , HooksEffectfulCBs, Effemore, Cache              #
                         , Installations                                   )
from .Metrics     import   Metrics
from .Vars        import ( Var, __, Vars, VarsReifiers, Substitutions      #
                         , ReifiersAssumps, SymAssumps, CtxVarRichRepr     #
                         , VarDomains, DomainABC, FiniteDiscreteDomain     )
from .Unification import ( Unification, UnificationIterables               #
                         , UnificationIterablesTypeGuard                   )
from .Goals       import ( Succeed, Fail, Eq, Goal, GoalABC, And, Or       #
                         , HeurConjChainVars, HeurConjCardinality          #
                         , ConjunctiveHeuristic, DisjunctiveHeuristic      #
                         , discern_goals, discriminate_goals               )
from .Constraints import ( Constraints, ConstraintVarsABC, Neq, Distinct   #
                         , Notin, PositiveCardinalityProduct               )
from .Solvers     import   SolverABC, Solver
from .Relations   import ( FactsTable, FreshRel, HeurConjRelevance         #
                         , HeurFactsOrdRnd                                 )
from .BinPU       import ( uint8, uint8_not, uint8_add, uint8_diff         )
