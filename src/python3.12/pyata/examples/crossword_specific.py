#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from collections import defaultdict
from itertools import groupby, chain
from math import prod
from typing import Any, Literal, Self, cast

import click_completion, nltk  # pyright: ignore[reportMissingTypeStubs]
import humanize, loguru, rich, typer, numpy as np
import rich.console, rich.columns, rich.box, rich.live, rich.logging, \
    rich.panel, rich.pretty, rich.progress, rich.table, rich.traceback, \
        rich.markdown, rich.status

from pyata.core import (
    Ctx, NoCtx, And, Vars, Substitutions, Var,
    Solver, CtxRichRepr, TabRel, GoalCtxSizedVared,
    VarTypes, RelationSized, BroadcastKey, HooksBroadcasts
)

APP = typer.Typer(name='crossword_specific', pretty_exceptions_enable=False)

click_completion.init()  # type: ignore

STDOUT = rich.console.Console(log_path=False)
STDERR = rich.console.Console(stderr=True, log_path=False)

loguru.logger.configure(handlers=[dict(
    level="DEBUG",
    sink=rich.logging.RichHandler(
        console=STDERR,
        markup=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        tracebacks_width=300,
        locals_max_length=100
        ),
    format="{message}",)])

INF = loguru.logger.info
DBG = loguru.logger.debug

def pp_ctx(ctx: Ctx) -> str:
    return rich.pretty.pretty_repr(CtxRichRepr(
        ctx, ignore_facets={VarTypes}))

##############################################################################
# Example (Non-General)
# ---------------------
#
# A specific example to help the intuition of how the basic machinery works.
#_____________________________________________________________________________

# Starting with a fresh context
ctx: Ctx = NoCtx

# Let's get some fresh variables to work with.
# We'll represent words as arrays of uint8s, so these
# logical variable of type uint8 when ground.
ctx, vars = Vars.fresh(ctx, np.uint8, 100)
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
    [  0, _01,   0, _03,   0, _05,   0,   0,   0,   0 ],
    [_10, _11, _12, _13, _14, _15, _16, _17, _18, _19 ],
    [  0, _21,   0, _23,   0, _25,   0,   0,   0,   0 ],
    [_30, _31, _32, _33, _34, _35, _36, _37, _38,   0 ],
    [  0, _41,   0, _43,   0, _45,   0,   0,   0,   0 ],
    [_50, _51, _52, _53, _54, _55, _56, _57,   0,   0 ],
    [  0, _61,   0, _63,   0, _65,   0, _67,   0,   0 ],
]

# CROSSWORD: list[list[Var | Literal[0]]] = [
#     [  0, _01,   0, _03,   0,   0,   0,   0,   0,   0 ],
#     [_10, _11, _12, _13, _14, _15, _16, _17, _18, _19 ],
#     [  0, _21,   0, _23,   0,   0,   0,   0,   0,   0 ],
#     [_30, _31, _32, _33, _34, _35, _36, _37, _38,   0 ],
#     [  0, _41,   0, _43,   0,   0,   0,   0,   0,   0 ],
#     [_50, _51, _52, _53, _54, _55, _56, _57,   0,   0 ],
#     [  0, _61,   0, _63,   0,   0,   0,   0,   0,   0 ],
# ]

def contig_grps(lst: list[Var | Literal[0]]) -> list[list[Var]]:
    return [cast(list[Var], grp) for grp in (
        list(g) for _, g in groupby(lst, lambda x: x != 0))
            if len(grp) > 1 and grp[0] != 0]

DIAGONALS: list[list[Var]] = [
    [_01, _12, _23, _34, _45, _56, _67 ],
  # [_03, _14, _25, _36],
  # [_10, _21, _32, _43, _54, _65],
  # [_30, _41, _52, _63],
]
WORDS: list[list[Var]] = list(chain(*(
    [contig_grps(row) for row in CROSSWORD] +
    [contig_grps(col) for col in zip(*CROSSWORD)]
))) + DIAGONALS

DIAG_VAR_SET = set(chain(*DIAGONALS))

@APP.command()
def main() -> None:
    rich.traceback.install(show_locals=True, width=None, locals_max_length=20)
    global ctx
    
    def heuristic_cb(ctx: Ctx, key: BroadcastKey,
                        data: tuple[int, int, goals: Iterable[Goal]]
    ) -> Ctx:
        orig, new, goals = data
        DBG(f'Conjunction heuristic optimized ({
            humanize.scientific(orig, 2)} -> {humanize.scientific(new, 2)})'
            ' new order:')
        DBG(f'{rich.pretty.pretty_repr(goals)}')
        return ctx
    ctx = And.hook_heuristic(ctx, heuristic_cb)
        
    solver = CrosswordSolver(ctx, WORDS)
    
    INF('Running the solver.')
    with rich.live.Live(
        rich.panel.Panel.fit(str(solver),
                            title="Crossword"),
        auto_refresh=True,
        transient=False
    ) as live:
        
        n_solution: list[int] = [0]
        last_solution: list[tuple[str, ...] | None] = [None]

        def defs_table(solution: tuple[str, set[str]]) -> rich.table.Table:
            word, defs = solution
            tab = rich.table.Table(box=rich.box.SIMPLE_HEAD,
                                show_header=False)
            tab.add_column(justify='right', style='cyan')
            tab.add_column(max_width=80, no_wrap=True, style='magenta')
            for definition in defs:
                tab.add_row(word, definition)
            return tab

        def show() -> None:
            render = [rich.panel.Panel.fit(
                    f'{solver}',
                    title=f"Solution {humanize.intcomma(n_solution[0])}")]
            if n_solution[0]:
                tab = rich.table.Table(box=rich.box.SIMPLE_HEAD,
                                        show_header=False)
                tab.add_column(justify='center', style='cyan')
                tab.add_column(max_width=80, no_wrap=True, style='magenta',
                            justify='left')
                for word in last_solution[0]:
                    defs = solver.definitions[word]
                    text: list[str] = []
                    i = 0
                    for d in defs:
                        i += 1
                        text.append(f'{i}. {d}')
                    tab.add_row(word, '\n'.join(text))
                render.append(tab)
            cols = rich.columns.Columns(render) #, equal=True)
            live.update(cols, refresh=True)
        
        def per_sec_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            seconds_past, cur_time = data
            show()
            return ctx
        solver.hook_per_sec(per_sec_cb)

        # Solve
        for solution in solver:
            n_solution[0] += 1
            last_solution[0] = solution
            show()


def nltk_word_len_to_arr2d() -> tuple[
    dict[int, np.ndarray[tuple[int, int],
                         np.dtype[np.uint8]]],
         dict[str, set[str]]
]:
    def get_wordset() -> dict[str, set[str]]:
        wordnet = nltk.corpus.wordnet
        INF('Getting WordNet words, using NLTK.')
        wordset: dict[str, set[str]] = defaultdict(set)
        for synset in wordnet.all_synsets():
            for w in synset.lemma_names():
                if w.isalpha() and w.isascii():
                    w = w.replace('_', '')
                    w = w.upper()
                    wordset[w].add(synset.definition())
        return wordset

    wordset: dict[str, set[str]]
    try:
        wordset = get_wordset()
    except LookupError:
        INF('NLTK corpus WordNet not found. Downloading.')
        nltk.download('wordnet')  # type: ignore
        wordset = get_wordset()
    INF(f'Got {humanize.intcomma(len(wordset))} words.')

    wordlist_by_len: dict[int,
                          list[np.ndarray[tuple[int],
                                          np.dtype[np.uint8]]]
                          ] = defaultdict(list)
    for word in wordset:
        wordlist_by_len[len(word)].append(str_to_arr(word))
    
    arr2d_per_len: dict[int,
                        np.ndarray[tuple[int, int],
                                np.dtype[np.uint8]]] = {}
    for length, arrlist in wordlist_by_len.items():
        arr2d_per_len[length] = np.stack(arrlist)

    return arr2d_per_len, wordset

def str_to_arr(word: str) -> np.ndarray[Any, np.dtype[np.uint8]]:
    return np.frombuffer(word.encode(), dtype=np.uint8)

def arr_to_str(arr: np.ndarray[Any, np.dtype[np.uint8]]) -> str:
    return arr.tobytes().decode()


##############################################################################
# Demonstrating a custom solver.
#
class CrosswordSolver(Solver):
    # A 2D array of words (as uint8s) per word length.
    len_to_arr2d, definitions = nltk_word_len_to_arr2d()
    
    words: list[list[Var]]
    wordrels: list[RelationSized[Any]]
    subgoals: list[GoalCtxSizedVared]
    progress: rich.progress.Progress | None
    
    seen: set[tuple[str, ...]] = set()
    
    def __init__(self: Self, ctx: Ctx,
                 words: list[list[Var]],
                 progress: rich.progress.Progress | None = None
    ) -> None:
        def word_rel(id: int, *vars: Var) -> TabRel[np.dtype[np.uint8], Any]:
            return TabRel[np.dtype[np.uint8], Any](
                self.len_to_arr2d[len(vars)],
                name=f'word_{id}')
        self.ctx  = ctx
        self.words = words
        self.progress = progress
        self.wordrels = [word_rel(i, *word) for i, word in enumerate(words)]
        DBG(f'Word relations: {rich.pretty.pretty_repr(self.wordrels)}')
        total_size: int = prod(len(rel) for rel in self.wordrels)
        DBG(f'Naïve search-space size: {humanize.scientific(total_size, 2)}')
        self.subgoals = [rel(*word) for rel, word in zip(self.wordrels, words)]
        self.goal = And(*self.subgoals)
        self.vars = tuple(set(v for word in words for v in word))
        self.stream_iter = iter(self.goal(self.ctx))
        self.prep_ctx()
    
    def __solution__(self: Self) -> tuple[Ctx, tuple[str, ...]]:
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
        ret = tuple(sol)
        self.seen.add(ret)
        return self.ctx, ret
    
    def __repr__(self: Self) -> str:
        """Show the solver state."""
        lines: list[str] = []
        ctx = self.ctx
        for row in CROSSWORD:
            show: list[Any] = []
            for cell in row:
                if isinstance(cell, Var):
                    ctx, val = Substitutions.walk(ctx, cell)
                    show.append(f"{'⸤' if cell in DIAG_VAR_SET else '['}")
                    show.append(f'{'_' if isinstance(val, Var) else val.tobytes().decode()}')
                    show.append(f"{'⸣' if cell in DIAG_VAR_SET else ']'}")
                else:
                    show.append("   ")
            lines.append("".join(str(s) for s in show))
        return "\n".join([f' {line} ' for line in lines])

if __name__ == '__main__':
    APP()

