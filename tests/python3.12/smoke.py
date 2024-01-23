
from pytest import mark

from pyata.immutables import *

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
