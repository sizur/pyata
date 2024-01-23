#!/usr/bin/env python3.12
# pyright: reportUnusedClass=false


from typing import Iterable, TypeGuard


__all__: list[str] = [
    'Cel', 'Nnl',
    'cons_is_empty', 'cons_is_not_empty', 'cons_from_iterable',
    'cons_to_iterable', 'cons_reverse', 'cons_to_reverse_iterable',
    'cons_to_list', 'cons_last'
]


type Cel[T] = tuple[T, Cel[T]] | tuple[()]
"""### A classic cons cell list type, with a tuple as the base type.
Efficient, fast, and :strong:`immutable` O(1) push and pop FILO stack."""

type Nnl[T] = tuple[T, Cel[T]]
"""### A not-empty cons cell list type, with a tuple as the base type.
A convenience type for non-empty defaults of `Cel[T]`, enabling
to skip some unnecessary checks for emptiness."""


def cons_is_empty[T](cell: Cel[T]) -> TypeGuard[Cel[T]]:
    return cell == ()


def cons_is_not_empty[T](cell: Cel[T]) -> TypeGuard[Nnl[T]]:
    return cell != ()


def cons_from_iterable[T](iterable: Iterable[T]) -> Cel[T]:
    """Reverse-order Cons from iterable."""
    cell: Cel[T] = ()
    for item in iterable:
        cell = (item, cell)
    return cell


def cons_to_iterable[T](cell: Cel[T]) -> Iterable[T]:
    car: T
    cdr: Cel[T]
    empty: Cel[T] = ()
    # TypeGuard is too expensive to use here.
    # while cons.is_not_empty(cell):
    while cell != empty:
        car, cdr = cell  # type: ignore
        yield car
        cell = cdr


def cons_reverse[T](cell: Cel[T]) -> Cel[T]:
    return cons_from_iterable(cons_to_iterable(cell))


def cons_to_reverse_iterable[T](cell: Cel[T]) -> Iterable[T]:
    return cons_to_iterable(cons_reverse(cell))


def cons_to_list[T](cell: Cel[T]) -> list[T]:
    """List from Cons in order cons would have been constructed from."""
    return list(cons_to_reverse_iterable(cell))


# This requires so many type-ignores...  (T_T)
def cons_last[T](cell: Nnl[T]) -> T:
    """Last item in Cons."""
    car: T
    cdr: Cel[T]
    # Cons can be emoty after looping once.
    cell_: Cel[T] = cell
    empty: Cel[T] = ()
    # TypeGuard is too expensive to use here.
    # while cons.is_not_empty(cell):
    while cell_ != empty:
        car, cdr = cell
        cell_ = cdr
    # car cannot be unboud, since we started with a NonEmptyCons.
    return car  # type: ignore
