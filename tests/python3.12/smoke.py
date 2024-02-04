
from pytest import mark

from rich.pretty import pretty_repr

from pyata.immutables import *
from pyata.core import *
from immutables import Map

pytestmark = mark.smoke

def test_cons():
    assert cons_is_empty(())
    assert not cons_is_not_empty(())
    assert cons_is_not_empty((1, ()))
    assert not cons_is_empty((1, ()))
    assert [1, 2, 3] == list(cons_to_iterable((1, (2, (3, ())))))
    assert (1, (2, (3, ()))) == cons_reverse((3, (2, (1, ()))))
    assert [3, 2, 1] == list(cons_to_reverse_iterable((1, (2, (3, ())))))
    assert (3, (2, (1, ()))) == cons_from_iterable([1, 2, 3])
    assert [1, 2, 3] == cons_to_list(cons_from_iterable([1, 2, 3]))
    assert [1, 2, 3] == cons_to_list((3, (2, (1, ()))))
    assert [3, 2, 1] == cons_to_list(cons_reverse((3, (2, (1, ())))))

def test_Set():
    assert Set() == Set()
    assert Set() != Set([1])
    assert Set([1]) == Set([1])
    assert Set([1]) == {1}
    assert Set([1]) != {2}
    assert Set([1]) != (1)
    assert Set([1]) == [1]
    assert Set([1]) == (1,)
    assert Set([1]) != (1, 2)
    assert Set[int]().add(1).add(2) == {1, 2}
    assert Set([1]).add(2) == {1, 2}
    assert Set([1]).discard(1) == Set()
    assert Set([1]).discard(2) == Set([1])
    assert Set([1]).union(Set([2])) == {1, 2}
    assert Set([1]).union(Set([1])) == {1}
    assert Set([1]).union(Set([1, 2])) == {1, 2}
    assert Set[int]().add(1).add(1) == {1}
    assert {1, 2} | Set([3]) == {1, 2, 3}
    assert {1, 2} | Set([1]) == {1, 2}
    assert {1, 2} == Set([1, 2])
    assert [1, 2] == Set({1, 2})
    assert {1,2,3} & Set([1, 2]) == {1, 2}
    s1 = Set([1])
    def f(m: SetMutation[int]) -> None:
        m.add(2)
        m.add(3)
        m.discard(1)
    assert s1.mutate(f) == {2, 3}
    assert s1 == {1}
    assert id(Set([1])) != id(Set([1]))
    assert id(Set[int]()) == id(Set[int]())
    # Python runtime is still typeless
    assert id(Set[int]()) == id(Set[str]())

def test_Facets():
    class F1(FacetABC[str, str]):
        default = 'default'
    class F2(FacetABC[int, int]):
        default = 0
    
    ctx = NoCtx
    
    assert F1.get(ctx, 'key') == 'default'
    assert F1.get_whole(ctx) == Map()
    assert F1.set(ctx, 'key', 'val') == Map({F1: Map({'key': 'val'})})
    assert F1.get_whole(ctx) == Map()
    assert F2.set(ctx, 1, 2) == Map({F2: Map({1: 2})})
    ctx = F2.set(ctx, 2, 3)
    ctx = F1.set(ctx, 'key', 'val')
    assert F1.get_whole(ctx) == Map({'key': 'val'})
    assert F2.get_whole(ctx) == Map({2: 3})
    def mutator(m: MapMutation[str, str]) -> None:
        m['key'] = 'val2'
        m['key2'] = 'val3'
    ctx = F1.mutate(ctx, mutator)
    assert ctx == Map({F1: Map({'key': 'val2', 'key2': 'val3'}), F2: Map({2: 3})})

def test_EventHooks():
    ctx = NoCtx
    flag = [0]
    def event_cb(ctx: Ctx, data: int) -> Ctx:
        flag[0] += data
        return ctx
    event_key1, event_key2 = object(), object()
    ctx = HooksEvents.hook(ctx, event_key1, event_cb)
    assert flag[0] == 0
    ctx = HooksEvents.run(ctx, event_key1, 1)
    assert flag[0] == 1
    ctx = HooksEvents.run(ctx, event_key2, 1)
    assert flag[0] == 1
    ctx = HooksEvents.run(ctx, event_key1, 2)
    assert flag[0] == 3
    # second hook on same key
    ctx = HooksEvents.hook(ctx, event_key1, event_cb)
    assert flag[0] == 3
    ctx = HooksEvents.run(ctx, event_key2, 1)
    assert flag[0] == 3
    ctx = HooksEvents.run(ctx, event_key1, 4)
    assert flag[0] == 11

expected_CtxRichRepr = """Ctx(
    HooksEvents(
        test_CtxRichRepr.<locals>.event_key(
            'test_CtxRichRepr.event_cb2',
            'test_CtxRichRepr.event_cb1'
        )
    )
)"""
def test_CtxRichRepr():
    ctx: Ctx = Map()
    assert pretty_repr(CtxRichRepr(ctx)) == 'Ctx()'
    def event_cb1(ctx: Ctx, data: int) -> Ctx: return ctx
    def event_cb2(ctx: Ctx, data: int) -> Ctx: return ctx
    def event_key(): return None
    ctx = HooksEvents.hook(ctx, event_key, event_cb1)
    ctx = HooksEvents.hook(ctx, event_key, event_cb2)
    assert pretty_repr(
        CtxRichRepr(ctx)) == expected_CtxRichRepr

def test_PipelineHooks():
    ctx: Ctx = Map()
    class F1(FacetABC[int, int]):
        default = 0
    some_F1_key = 1
    
    def acc_cb(ctx: Ctx, data: int) -> tuple[Ctx, int]:
        item = F1.get(ctx, some_F1_key)
        data += item
        ctx = F1.set(ctx, some_F1_key, data)
        return ctx, data
    
    side_acc = [0]
    def side_cb(ctx: Ctx, data: int) -> tuple[Ctx, int]:
        data *= 2
        side_acc[0] += data
        return ctx, data
    
    class PipelineKey1: pass
    def pipeline_key2(): pass
    
    ctx = HooksPipelines.hook(ctx, PipelineKey1, side_cb)
    ctx = HooksPipelines.hook(ctx, PipelineKey1, acc_cb)
    
    ctx, val = HooksPipelines.run(ctx, PipelineKey1, 1)
    assert val == 2
    assert F1.get(ctx, some_F1_key) == 1
    assert side_acc[0] == 2
    
    ctx, val = HooksPipelines.run(ctx, PipelineKey1, 1)
    assert val == 4
    assert F1.get(ctx, some_F1_key) == 2
    assert side_acc[0] == 6
    
    ctx, val = HooksPipelines.run(ctx, PipelineKey1, 10)
    assert val == 24
    assert F1.get(ctx, some_F1_key) == 12
    assert side_acc[0] == 30

    # not hooked pipeline
    ctx, val = HooksPipelines.run(ctx, pipeline_key2, 100)
    assert val == 100                     # passthrough
    assert F1.get(ctx, some_F1_key) == 12 # unchanged
    assert side_acc[0] == 30              # unchanged


def test_BroadcastHooks():
    ...


expected = """Ctx(
    Constraints(
        x={Neq(Violation(), x=1, y=1)},
        y={Neq(Violation(), x=1, y=1)}
    ),
    Substitutions(x=1, y=1)
)"""
def test_Neq_repr():
    ctx = NoCtx
    x = Var('x')
    y = Var('y')
    neq = Neq(x, y)
    assert pretty_repr(neq) == 'Neq(x, y)'
    ctx = neq.constrain(ctx)
    assert ctx is not Unification.Failed
    assert neq(ctx) is not Unification.Failed
    assert pretty_repr(CtxRichRepr(ctx)
        ) == "Ctx(Constraints(x={Neq(x, y)}, y={Neq(x, y)}))"
    ctx = Substitutions.sub(ctx, y, 1)
    assert pretty_repr(CtxRichRepr(ctx)
        ) == 'Ctx(Constraints(x={Neq(x, y=1)}, y={Neq(x, y=1)}), Substitutions(y=1))'
    ctx = Substitutions.sub(ctx, x, 2)
    assert pretty_repr(CtxRichRepr(ctx)
        ) == 'Ctx(Constraints(x={Neq(x=2, y=1)}, y={Neq(x=2, y=1)}), Substitutions(x=2, y=1))'
    ctx = Substitutions.sub(ctx, x, 1)
    assert pretty_repr(CtxRichRepr(ctx)) == expected
    

def test_iterable_unification():
    ctx = NoCtx
    ctx = Unification.hook_unify(ctx, UnificationIterables.unify_hook)
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, 1, 1)
    assert ctx is not Unification.Failed
    ctxF = Unification.unify(ctx, 1, 2)
    assert ctxF is Unification.Failed
    ctx = Unification.unify(ctx, [1], [1])
    assert ctx is not Unification.Failed
    ctxF = Unification.unify(ctx, [1], [2])
    assert ctxF is Unification.Failed
    ctx = Unification.unify(ctx, [1, 2], [1, 2])
    assert ctx is not Unification.Failed
    ctxF = Unification.unify(ctx, [1, 2], [1, 3])
    assert ctxF is Unification.Failed
    ctxF = Unification.unify(ctx, [1, 2], [1])
    assert ctxF is Unification.Failed
    ctxF = Unification.unify(ctx, [1], [1, 2])
    assert ctxF is Unification.Failed
    ctxF = Unification.unify(ctx, [1], [])
    assert ctxF is Unification.Failed
    ctxF = Unification.unify(ctx, [], [1])
    assert ctxF is Unification.Failed
    ctx = Unification.unify(ctx, [], [])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, [1, 2], [1, ...])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, [1, ...], [1, 2])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, [1, 2, 3], [1, ...])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, [1, ...], [1, 2, 3])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx, [1, ...], [1, ...])
    assert ctx is not Unification.Failed
    var = Var('var')
    ctx = Unification.unify(ctx, [1, 2, 3], [1, var, 3])
    assert ctx is not Unification.Failed
    ctx, val = Substitutions.walk(ctx, var)
    assert val == 2
    ctx = Unification.unify(ctx, [1, var, 3], [1, 2, 3])
    assert ctx is not Unification.Failed
    ctx, val = Substitutions.walk(ctx, var)
    assert val == 2
    ctxF = Unification.unify(ctx, [1, 2, var], [1, 2, 3])
    assert ctxF is Unification.Failed
    var2 = Var('var2')
    ctx = Unification.unify(ctx,
                            [[0, 1], [3, var2, ...], [7, 8]],
                            [[0, 1], [3, [4, 5], 6], ...])
    assert ctx is not Unification.Failed
    ctx, val = Substitutions.walk(ctx, var2)
    assert val == [4, 5]
    ctx = Unification.unify(ctx,
                            [[0, 1], [3, [4, 5], 6], ...],
                            [[0, 1], [3, var2, ...], [7, 8]])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx,
                            [[0, 1], [__, [4, 5], 6], ...],
                            [[0, 1], [3, var2, ...], [7, 8]])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx,
                            [[0, 1], [3, [4, 5], 6], ...],
                            [[0, 1], [__, var2, ...], [7, 8]])
    assert ctx is not Unification.Failed
    ctx = Unification.unify(ctx,
                            [[0, 1], [__, [4, 5], 6], ...],
                            [[0, 1], [__, var2, ...], [7, 8]])
    assert ctx is not Unification.Failed
    
    # Iterables without a type guard
    ctx = Unification.unify(ctx,
                            [[0, 1], [3, [4, 5], 6], ...],
                            ((0, 1), (3, var2, ...), (7, 8)))
    assert ctx is not Unification.Failed

    # Iterables with a type guard
    ctx = Unification.hook_unify(ctx, UnificationIterablesTypeGuard.unify_hook)
    assert ctx is not Unification.Failed
    ctxF = Unification.unify(ctx,
                            [[0, 1], [3, [4, 5], 6], ...],
                            ((0, 1), (3, var2, ...), (7, 8)))
    assert ctxF is Unification.Failed
    ctx = Unification.unify(ctx,
                            [[0, 1], [3, [4, 5], 6], ...],
                            [[0, 1], [3, var2, ...], [7, 8]])
    assert ctx is not Unification.Failed
