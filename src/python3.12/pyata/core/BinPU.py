#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from inspect import signature
from itertools import product
from typing import Callable, Final, Self

import numpy as np

# from pyata.core.Vars import Substitutions

# from .Constraints import ConstraintVarsABC
from .Goals import And
from .Types import GoalVared, GoalCtxSizedVared, Arg #, Ctx, Var
from .Relations import FactsTable, FreshRel


__all__: list[str] = [
    'uint8', 'uint8_not', 'uint8_add', 'uint8_diff',
]


type Bit   = Arg[int]  #  1-bit: 0 or 1
type Hex   = Arg[int]  #  4-bit: 0 to 15
type Byte  = Arg[int]  #  8-bit: 0 to 255
type Word  = Arg[int]  # 16-bit: 0 to 65_535
type DWord = Arg[int]  # 32-bit: 0 to 4_294_967_295
type QWord = Arg[int]  # 64-bit: 0 to 18_446_744_073_709_551_615


class HexRel[*T](FactsTable[np.dtype[np.uint8], *T]):
    """Generic class of hexadecimal tabulated relations."""
    def __init__(self: Self,
                 name: str,
                 mapper: Callable[..., tuple[int, ...] | None]
    ) -> None:
        mapper_arity = len(signature(mapper).parameters)
        arr = np.array([
            np.array(fact, dtype=np.uint8) for fact in (
                mapper(*args) for args in product(
                    *(range(16) for _ in range(mapper_arity))))
            if fact is not None])
        super().__init__(arr, name, is_static=True)


######################################################################
# hex_bits(14, 1, 1, 1, 0)

def hex_bits_mapper(h: int) -> tuple[int, ...]:
    return (h, *((h >> i) & 1 for i in range(3, -1, -1)))

HEX_BITS_REL: Final[HexRel[Hex, Bit, Bit, Bit, Bit]] = HexRel(
    'HEX_BITS', hex_bits_mapper)

def hex_bits(h: Hex, b3: Bit, b2: Bit, b1: Bit, b0: Bit) -> GoalCtxSizedVared:
    return HEX_BITS_REL(h, b3, b2, b1, b0)

######################################################################
# uint4_add (14, 1, 15, 0)
# uint4_diff(14, 1, 13, 0)

def uint4_add_mapper(a: int, b: int) -> tuple[int, ...]:
    return (a, b, (a + b) % 16, (a + b) // 16)

UINT4_ADD_REL: Final[HexRel[Hex, Hex, Hex, Hex]] = HexRel(
    'UINT4_ADD', uint4_add_mapper)

def uint4_add(augend: Hex, addend: Hex, sum: Hex, carry: Hex
              ) -> GoalCtxSizedVared:
    return UINT4_ADD_REL(augend, addend, sum, carry)

def uint4_diff(minuend: Hex, subtrahend: Hex, diff: Hex, borrow: Hex
               ) -> GoalCtxSizedVared:
    return UINT4_ADD_REL(diff, subtrahend, minuend, borrow)

######################################################################
# uint4_mul   ( 4, 3, 12, 0)
# uint4_divmod(14, 3,  4, 2)

def uint4_mul_mapper(a: int, b: int) -> tuple[int, ...]:
    return (a, b, (a * b) % 16, (a * b) // 16)

def uint4_divmod_mapper(a: int, b: int) -> tuple[int, ...] | None:
    return None if b == 0 else (a, b, (a // b), (a % b))

UINT4_MUL_REL: Final[HexRel[Hex, Hex, Hex, Hex]] = HexRel(
    'UINT4_MUL', uint4_mul_mapper)

UINT4_DIVMOD_REL: Final[HexRel[Hex, Hex, Hex, Hex]] = HexRel(
    'UINT4_DIVMOD', uint4_divmod_mapper)

def uint4_mul(multiplicand: Hex, multiplier: Hex, product: Hex, cycles: Hex
              ) -> GoalCtxSizedVared:
    return UINT4_MUL_REL(multiplicand, multiplier, product, cycles)

def uint4_divmod(dividend: Hex, divisor: Hex, quotient: Hex, remainder: Hex
                 ) -> GoalCtxSizedVared:
        return UINT4_DIVMOD_REL(dividend, divisor, quotient, remainder)

######################################################################
# uint4_and(5, 3, 1)        # 0101 & 0011 = 0001
# uint4_or (5, 3, 7)        # 0101 | 0011 = 0111
# uint4_xor(5, 3, 6)        # 0101 ^ 0011 = 0110
# uint4_not(5, 10)          #      ~ 0101 = 1010
# uint4_lshift(5, 2, 4, 1)  # 0101 << 010 = 0100 (0001)
# uint4_rshift(5, 2, 1, 4)  # 0101 >> 010 = 0001 (0100)

def uint4_and_mapper(a: int, b: int) -> tuple[int, ...]:
    return (a, b, a & b)

def uint4_or_mapper(a: int, b: int) -> tuple[int, ...]:
    return (a, b, a | b)

def uint4_xor_mapper(a: int, b: int) -> tuple[int, ...]:
    return (a, b, a ^ b)

def uint4_not_mapper(a: int) -> tuple[int, ...]:
    return (a, ~a & 0xf)

def uint4_lshift_mapper(a: int, b: int) -> tuple[int, ...] | None:
    return None if b > 4 else (a, b, a << b, a >> (4 - b))

def uint4_rshift_mapper(a: int, b: int) -> tuple[int, ...] | None:
    return None if b > 4 else (a, b, a >> b, a << (4 - b))

UINT4_AND_REL: Final[HexRel[Hex, Hex, Hex]] = HexRel(
    'UINT4_AND', uint4_and_mapper)

UINT4_OR_REL: Final[HexRel[Hex, Hex, Hex]] = HexRel(
    'UINT4_OR', uint4_or_mapper)

UINT4_XOR_REL: Final[HexRel[Hex, Hex, Hex]] = HexRel(
    'UINT4_XOR', uint4_xor_mapper)

UINT4_NOT_REL: Final[HexRel[Hex, Hex]] = HexRel(
    'UINT4_NOT', uint4_not_mapper)

UINT4_LSHIFT_REL: Final[HexRel[Hex, Hex, Hex, Hex]] = HexRel(
    'UINT4_LSHIFT', uint4_lshift_mapper)

UINT4_RSHIFT_REL: Final[HexRel[Hex, Hex, Hex, Hex]] = HexRel(
    'UINT4_RSHIFT', uint4_rshift_mapper)

def uint4_and(a: Hex, b: Hex, ab: Hex) -> GoalCtxSizedVared:
    return UINT4_AND_REL(a, b, ab)

def uint4_or(a: Hex, b: Hex, ab: Hex) -> GoalCtxSizedVared:
    return UINT4_OR_REL(a, b, ab)

def uint4_xor(a: Hex, b: Hex, ab: Hex) -> GoalCtxSizedVared:
    return UINT4_XOR_REL(a, b, ab)

def uint4_not(a: Hex, not_a: Hex) -> GoalCtxSizedVared:
    return UINT4_NOT_REL(a, not_a)

def uint4_lshift(a: Hex, lshift: Hex, shifted: Hex, overflow: Hex
                 ) -> GoalCtxSizedVared:
    return UINT4_LSHIFT_REL(a, lshift, shifted, overflow)

def uint4_rshift(a: Hex, rshift: Hex, shifted: Hex, overflow: Hex
                 ) -> GoalCtxSizedVared:
    return UINT4_RSHIFT_REL(a, rshift, shifted, overflow)


######################################################################
# uint8 relations

def uint8_mapper(hi: int, lo: int) -> tuple[int, ...]:
    return (hi, lo, (hi << 4) + lo)

def uint8_not_mapper(hi: int, lo: int) -> tuple[int, ...]:
    mk = (hi << 4) + lo
    return (mk, ~mk & 0xff)

UINT8_REL: Final[HexRel[Hex, Hex, Byte]] = HexRel(
    'UINT8', uint8_mapper)

UINT8_NOT_REL: Final[HexRel[Byte, Byte]] = HexRel(
    'UINT8_NOT', uint8_not_mapper)

def uint8(hi: Hex, lo: Hex, mk: Byte) -> GoalCtxSizedVared:
    return UINT8_REL(hi, lo, mk)

def uint8_not(a: Hex, not_a: Byte) -> GoalCtxSizedVared:
    return UINT8_NOT_REL(a, not_a)

def uint8_add(a: Byte, b: Byte, sum: Byte, carry: Hex
              ) -> GoalVared:
    # s: sum, c: carry, i: intermediate
    def rel(a_lo: Hex, b_lo: Hex, s_lo: Hex, c_lo: Hex,
            a_hi: Hex, i_hi: Hex, ic_hi: Hex,
            b_hi: Hex, s_hi: Hex, c_hi: Hex
    ) -> And:
        return And(
            uint8(a_hi, a_lo, a),
            uint8(b_hi, b_lo, b),
            uint4_add(a_lo, b_lo, s_lo, c_lo),
            uint4_add(c_lo, a_hi, i_hi, ic_hi),
            uint4_add(i_hi, b_hi, s_hi, c_hi),
            uint4_add(ic_hi, c_hi, carry, 0),
            uint8(s_hi, s_lo, sum)
        )
    return FreshRel(int, 10)(rel)

def uint8_diff(minuend: Byte, subtrahend: Byte, diff: Byte, borrow: Hex
               ) -> GoalVared:
     return uint8_add(diff, subtrahend, minuend, borrow)

# class UintBinSplit(ConstraintVarsABC):
#     def __init__(self: Self, n_hi: int, n_lo: int,
#                  hi: Arg[int], lo: Arg[int], mk: Arg[int]) -> None:
#         self.n_hi = n_hi
#         self.n_lo = n_lo
#         self.hi = hi
#         self.lo = lo
#         self.mk = mk
#         self.vars = tuple(v for v in (hi, lo, mk) if isinstance(v, Var))
    
#     def __call__(self: Self, ctx: Ctx) -> Ctx:
#         hi, lo, mk = ((Substitutions.walk(ctx, i)
#                        if isinstance(i, Var) else i)
#                       for i in (self.hi, self.lo, self.mk))
#         if isinstance(mk, int):
#             mk_hi = (mk >> self.n_lo) & ((1 << self.n_hi) - 1)
#             mk_lo = mk & ((1 << self.n_lo) - 1)


# def uint16(hi: Byte, lo: Byte, mk: Word) -> GoalCtxSizedVared:
#     def rel(hi_hi: Hex, hi_lo: Hex, lo_hi: Hex, lo_lo: Hex, mk_hi: Hex, mk_lo: Hex
#     ) -> And:
#         return And(
#             uint8(hi_hi, hi_lo, hi),
#             uint8(lo_hi, lo_lo, lo),
#             uint8(mk_hi, mk_lo, mk)
        

# def uint16_add(a: Word, b: Word, sum: Word, carry: Hex
#                ) -> GoalVared:
#     # s: sum, c: carry, i: intermediate
#     def rel(a_lo: Byte, b_lo: Byte, s_lo: Byte, c_lo: Hex,
#             a_hi: Byte, i_hi: Byte, ic_hi: Hex,
#             b_hi: Byte, s_hi: Byte, c_hi: Hex
#     ) -> And:
#         return And(
#             uint8(a_hi, a_lo, a),
#             uint8(b_hi, b_lo, b),
#             uint8_add(a_lo, b_lo, s_lo, c_lo),
#             uint8_add(c_lo, a_hi, i_hi, ic_hi),
#             uint8_add(i_hi, b_hi, s_hi, c_hi),
#             uint8_add(ic_hi, c_hi, carry, 0),
#             uint8(s_hi, s_lo, sum)
#         )
#     return FreshRel(int, 10)(rel)
