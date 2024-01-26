#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from collections import defaultdict
from itertools import groupby, chain
from typing import Any, Literal, Self, cast

import humanize       as HI
import nltk           as NL  # pyright: ignore[reportMissingTypeStubs]
import numpy          as NP
import loguru         as LG
import rich.box       as RX
import rich.live      as RV
import rich.logging   as RL
import rich.panel     as RP
import rich.pretty    as RY
import rich.table     as RT
import rich.traceback as RB
import typer          as TR

from pyata.core import (
    Ctx, NoCtx, And, Vars, Substitutions, Var,
    Solver, CtxRichRepr, NDArrayRel, GoalSizedVared
)

RB.install()
LG.logger.configure(handlers=[dict(
    level="DEBUG",
    sink=RL.RichHandler(
        markup=True,
        show_path=False,),
    format="{message}",)])
INFO = LG.logger.info
DEBUG = LG.logger.debug

def pretty_ctx(ctx: Ctx) -> str:
    return RY.pretty_repr(CtxRichRepr(ctx))

##############################################################################
# Example (Non-General)
# ---------------------
#
# A specific example to help the intuition of how the basic machinery works.
#_____________________________________________________________________________

# Starting with a fresh context
ctx: Ctx = NoCtx
# Can inspect it during debugging.
INFO(f'Fresh context: {pretty_ctx(ctx)}')

# Let's get some fresh variables to work with.
# We'll represent words as arrays of uint8s, so these
# logical variable of type uint8 when ground.
INFO('Getting fresh variables:')
ctx, vars = Vars.fresh(ctx, NP.uint8, 100)
(
    _00,_01, _02, _03, _04, _05, _06, _07, _08, _09,
    _10,_11, _12, _13, _14, _15, _16, _17, _18, _19,
    _20,_21, _22, _23, _24, _25, _26, _27, _28, _29,
    _30,_31, _32, _33, _34, _35, _36, _37, _38, _39,
    _40,_41, _42, _43, _44, _45, _46, _47, _48, _49,
    _50,_51, _52, _53, _54, _55, _56, _57, _58, _59,
    _60,_61, _62, _63, _64, _65, _66, _67, _68, _69,
    _70,_71, _72, _73, _74, _75, _76, _77, _78, _79,
    _80,_81, _82, _83, _84, _85, _86, _87, _88, _89,
    _90,_91, _92, _93, _94, _95, _96, _97, _98, _99,
) = vars

CROSSWORD: list[list[Var | Literal[0]]] = [
    [  0, _01,   0,   0,   0,   0,   0, _07 ],
    [_10, _11, _12, _13, _14, _15, _16, _17 ],
    [  0, _21,   0, _23,   0, _25,   0, _27 ],
    [  0, _31, _32, _33, _34, _35, _36, _37 ],
    [  0, _41,   0, _43,   0, _45,   0, _47 ],
    [  0, _51, _52, _53, _54, _55, _56, _57 ],
    [  0, _61,   0, _63,   0, _65,   0,   0 ],
    [_70, _71, _72, _73, _74, _75, _76, _77 ],
]

def contig_grps(lst: list[Var | Literal[0]]) -> list[list[Var]]:
    return [cast(list[Var], grp) for grp in (
        list(g) for _, g in groupby(lst, lambda x: x != 0))
            if len(grp) > 1 and grp[0] != 0]

WORDS = list(chain(*(
    [contig_grps(row) for row in CROSSWORD] +
    [contig_grps(col) for col in zip(*CROSSWORD)]
)))

def main() -> None:
    INFO('Constructing the solver.')
    solver = CrosswordSolver(ctx, WORDS)
    
    INFO('Running the solver.')
    with RV.Live(RP.Panel.fit(str(solver), title="Crossword"),
                 auto_refresh=True,
                 transient=False
    ) as live:
        
        n_solution = 0
        
        # Solve
        for (solution,) in solver:
            n_solution += 1
            overtab = RT.Table(box=RX.SIMPLE_HEAD)
            overtab.add_column(f'Solution {n_solution}\n'
                               f'Duplicate solutions: {n_solution - len(solver.seen)}',
                               style='green')
            overtab.add_column()
            tab = RT.Table(box=RX.SIMPLE_HEAD)
            tab.add_column('Word', justify='right', style='cyan')
            tab.add_column('Definition', style='magenta')
            for word, definition in sorted(solution.items()):
                tab.add_row(word, definition)
            overtab.add_row(RP.Panel.fit(str(solver), title="Crossword"),
                            tab)
            live.update(overtab)


def nltk_word_len_to_arr2d() -> tuple[
    dict[int, NP.ndarray[tuple[int, int],
                         NP.dtype[NP.uint8]]],
         dict[str, str]
]:
    def get_wordset() -> tuple[set[str], dict[str, str]]:
        WN = NL.corpus.wordnet
        INFO('Getting a set of nouns using NLTK.')
        wordset: set[str] = set()
        definitions: dict[str, str] = {}
        for synset in WN.all_synsets(pos=WN.NOUN):
            for w in synset.lemma_names():
                if ('_' not in w and w.isalpha() and w.isascii()
                    and w not in wordset):
                    wordset.add(w)
                    definitions[w] = synset.definition()
        return wordset, definitions

    wordset: set[str] = set()
    definitions: dict[str, str] = {}
    try:
        wordset, definitions = get_wordset()
    except LookupError:
        NL.download('wordnet')  # type: ignore
        wordset, definitions = get_wordset()
    INFO(f'Got {HI.intcomma(len(wordset))} words.')

    wordlist_by_len: dict[int,
                          list[NP.ndarray[tuple[int],
                                          NP.dtype[NP.uint8]]]
                          ] = defaultdict(list)
    for word in wordset:
        wordlist_by_len[len(word)].append(str_to_arr(word))
    INFO(f'Words lengths: '
        f'{dict(sorted((
            (len(wordlist_by_len[k]), k) for k in wordlist_by_len),
            reverse=True))}')

    arr2d_per_len: dict[int,
                        NP.ndarray[tuple[int, int],
                                NP.dtype[NP.uint8]]] = {}
    for length, arrlist in wordlist_by_len.items():
        arr2d_per_len[length] = NP.stack(arrlist)

    return arr2d_per_len, definitions

def str_to_arr(word: str) -> NP.ndarray[Any, NP.dtype[NP.uint8]]:
    return NP.frombuffer(word.encode(), dtype=NP.uint8)

def arr_to_str(arr: NP.ndarray[Any, NP.dtype[NP.uint8]]) -> str:
    return arr.tobytes().decode()


##############################################################################
# Demonstrating a custom solver.
#
class CrosswordSolver(Solver):
    # A 2D array of words (as uint8s) per word length.
    len_to_arr2d, definitions = nltk_word_len_to_arr2d()
    
    words: list[list[Var]]
    subgoals: list[GoalSizedVared]
    
    seen: set[tuple[str, ...]] = set()
    
    def __init__(self: Self, ctx: Ctx, words: list[list[Var]]) -> None:
        def word_goal(*vars: Var) -> GoalSizedVared:
            return NDArrayRel(self.len_to_arr2d[len(vars)])(*vars)
        self.ctx  = ctx
        self.words = words
        self.subgoals = [word_goal(*word) for word in words] 
        self.heuristic()
        self.goal = And(*self.subgoals)
        self.vars = tuple(set(v for word in words for v in word))
        self.stream_iter = iter(self.goal(ctx))
        self.prep_ctx()
    
    def heuristic(self: Self) -> None:
        # (higher number of shared vars, lower relation size)
        shared: dict[GoalSizedVared, int] = defaultdict(int)
        for goal in self.subgoals:
            for var in goal.vars:
                shared[goal] += sum(1 for g in self.subgoals if var in g.vars
                                    and g is not goal)
        self.subgoals.sort(key=lambda g: (-shared[g], len(g)))
        for i, goal in enumerate(self.subgoals):
            DEBUG(f'Goal {i}: shared vars: {shared[goal]}, '
                  f'size: {len(goal)} '
                  f'vars {goal.vars}')
    
    def __solution__(self: Self) -> tuple[Ctx, tuple[dict[str, str]]]:
        """Reconstruct a solutions from a solved context."""
        sol: list[str] = []
        for subgoal in self.subgoals:
            word: list[str] = []
            for var in subgoal.vars:
                self.ctx, val = Substitutions.walk(self.ctx, var)
                if isinstance(val, Var):
                    word = []
                    break
                word.append(val.tobytes().decode())
            if word:
                sol.append(''.join(word))
        self.seen.add(tuple(sol))
        return self.ctx, ({w: self.definitions[w] for w in sol},)
    
    def __repr__(self: Self) -> str:
        """Show the solver state."""
        lines: list[str] = []
        ctx = self.ctx
        for row in CROSSWORD:
            show: list[Any] = []
            for cell in row:
                if isinstance(cell, Var):
                    ctx, val = Substitutions.walk(ctx, cell)
                    if isinstance(val, Var):
                        show.append("⎵")
                    else:
                        show.append(val.tobytes().decode())
                else:
                    show.append(" ")
            lines.append(" ".join(str(s) for s in show))
        return "\n".join([f' {line} ' for line in lines])


run = TR.run(main)

