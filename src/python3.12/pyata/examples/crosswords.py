#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from itertools import groupby, chain
import time
from typing import Annotated, Any, Callable, ClassVar, Concatenate, Iterable, Literal, Self, TypeGuard, cast

import click_completion, nltk  # pyright: ignore[reportMissingTypeStubs]
import humanize, loguru, rich, typer, numpy as np
import rich.console, rich.columns, rich.box, rich.live, rich.logging, \
    rich.panel, rich.pretty, rich.progress, rich.table, rich.traceback, \
        rich.markdown, rich.status, rich.text, rich.padding

from pyata.core import (
    Ctx, NoCtx, And, Or, Vars, Substitutions, Var,
    Solver, CtxRichRepr, FactsTable, GoalCtxSizedVared,
    VarsReifiers, Goal, Notin, HooksBroadcasts, BroadcastKey
)

APP = typer.Typer(name='crossword_specific', pretty_exceptions_enable=False)

click_completion.init()  # type: ignore

STDOUT = rich.console.Console(log_path=False)
STDERR = rich.console.Console(
    stderr=True, log_path=False, tab_size=4, soft_wrap=True)

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

def LOG[T, **P](arg: T, dispatch: Callable[Concatenate[str, P], None],
                *logger_args: P.args, **logger_kwargs: P.kwargs) -> T:
    dispatch((arg if type(arg) is str
              else rich.pretty.pretty_repr(arg)),
             *logger_args, **logger_kwargs)
    return arg

# Log expression wrappers
def ERR[T](arg:T, *logger_args: Any, **logger_kwargs: Any) -> T:
    return LOG(arg, dispatch=loguru.logger.error, *logger_args, **logger_kwargs)
def DBG[T](arg: T, *logger_args: Any, **logger_kwargs: Any) -> T:
    return LOG(arg, dispatch=loguru.logger.debug, *logger_args, **logger_kwargs)
def INF[T](arg: T, *logger_args: Any, **logger_kwargs: Any) -> T:
    return LOG(arg, dispatch=loguru.logger.info, *logger_args, **logger_kwargs)
def NOP[T](arg: T, *_: Any, **__: Any) -> T:
    return arg

def CTX(ctx: Ctx) -> CtxRichRepr:
    return CtxRichRepr(ctx, ignore_facets={VarsReifiers})

##############################################################################
# A Crossword Example
# --------------------
#
# Crosswords really excercise conjunction performance to the extreme.
#
# Types of connective heuristics that can help conjunction performance
# can be divided into two categories:
#
#   1. Applicable to size-aware and var-aware goals:
#
#       - goal's unification order by lowest frequency of variable
#
#       - contextual Notin var constraint expanstion as soon as goal
#         exhausts a value for a variable.
#
#       - connective constructing pairwize goal search-space size
#         matrix, and ordering the goals based on that.
#
#       - connective constructing and running an order-search goal
#         based on shared variable goal pair chaining. A goal
#         dependency graph can be constructed from shared variables,
#         cliques collapsed, and topologically ordered combinations
#         enumerated with their resultant search-space sizes,
#         minimal kept, and search interrupted at possibly parametric
#         timeout or stability of minimal search-space size.
#
#   2. Applicable to size-unaware and/or var-unaware goals:
#
#       - a type of "lookahead", where connective will run each goal
#         individually first, gathering various stats about goal's
#         perf and context changes, then orders the goals based on
#         that and runs them in original context.
#         (this needs to be further subdivided)
#
#       - same as above but sample and cut sampling streams short.
#
# Connectives can freely mix goals of various awareness, resulting in
# a goal of optimiztic max awareness (with loss of accuracy),
# prioritizing the most aware subgoals first, since these are most
# optimizable.  FactTable relations produce the most aware goals,
# while still being general.
#
# Some types of these heuristics are already implemented, some partially,
# and others not yet.
#
#_____________________________________________________________________________

# Starting with a fresh context, install extensions and configure heuristics.
ctx: Ctx = NoCtx
# Randomized intratable factchecking order.
ctx = FactsTable.FactsGoal.hook_facts(ctx,
      FactsTable.heur_facts_ord_rnd)

# Let's define some explicit variables for special
# crossword word shapes.
(_A,_B,_C,_D,_E,_F,_G,_H,_I,_J,_K,_L,_M,_N,_O,_P,_Q,_R,_S,_T,
 _U,_V,_W,_X,_Y,_Z) = (
     Var(f'_{chr(i)}')for i in range(ord('A'), 1 + ord('Z')))
(_a,_b,_c,_d,_e,_f,_g,_h,_i,_j,_k,_l,_m,_n,_o,_p,_q,_r,_s,_t,
 _u,_v,_w,_x,_y) = (
     Var(f'_{chr(i)}') for i in range(ord('a'), 1 + ord('y')))


MIN_WORD_LEN  = 2
MAX_DEFINITIONS = 1
BIDIRECTIONAL = False  # does not apply to SPECIALS

_ = None
CROSSWORD: list[list[Var | int | None | str]] = [

    # - Any integers will become fresh unbound unique variables,
    #   regardless of integer value.
    # - Any single letter string literals will become fresh
    #   variables, bound to that capital letter's ASCII value.

    [_E ,_F ,_G , _ , _ , _ , _ , _ , _ , _ ,_f , _ , _ , _ , _ ],
    [_D , _ ,_H ,_K , _ ,_N ,_T ,_U , _ ,_c ,_d ,_e ,_k ,_l , _ ],
    [_C ,_J ,_I ,_L ,_M ,_O , _ ,_V ,_W , _ ,_g , _ , _ ,_m ,_n ],
    [_B , _ , _ , _ , _ ,_P ,_b , _ ,_X , _ ,_h , _ ,_s , _ ,_o ],
    [_A , _ , _ ,_S ,_R ,_Q ,_a ,_Z ,_Y , _ ,_i ,_j ,_r ,_q ,_p ],
    [ 0 , 0 , 0 ,_w ,_u , 0 , 0 ,_t ,_x , 0 ,_v , 0 ,_y , 0 , 0 ],
]
SPECIALS: list[list[Var]] = [
    
    # Any non-standard shapes are here
    
    [_A,_B,_C,_D,_E,_F,_G,_H,_I,_J],  # P
    [_K,_L,_M,_N,_O,_P,_Q,_R,_S],     # y
    [_T,_U,_V,_W,_X,_Y,_Z,_a,_b],     # a
    [_c,_d,_e,_f,_g,_h,_i,_j],        # t
    [_k,_l,_m,_n,_o,_p,_q,_r,_s],     # a
    # [_G,_K,_M,_P,_a,_t],                # (diagonals)
    # [_u,_Q,_b,_V],
    # [_v,_j,_s,_m],
]


# Fill-in the crossword ints with fresh variables,
# and the strings with fresh bound variables.
def fresh_cond(cell: Var | int | None | str) -> TypeGuard[int | str]:
    return isinstance(cell, (int, str))
num_fresh = sum(1 for row in CROSSWORD for cell in row
                if fresh_cond(cell))
if num_fresh:
    ctx, frech_vars = Vars.fresh(ctx, chr, num_fresh)
    fresh_itr = iter(frech_vars)
    for i in range(len(CROSSWORD)):
        for j in range(len(CROSSWORD[i])):
            cell = CROSSWORD[i][j]
            if fresh_cond(cell):
                var = next(fresh_itr)
                if isinstance(cell, str):
                    assert len(cell) == 1
                    assert cell.isalpha()
                    ctx = Substitutions.sub(ctx, var, ord(cell.upper()))
                CROSSWORD[i][j] = var
            elif isinstance(cell, Var):
                ctx, conflict = Vars.contextualize(
                    ctx, chr, cell)

def crossword_typenarrow(mtx: list[list[Var | int | None | str]]
                         ) -> TypeGuard[list[list[Var | None]]]:
    return all((isinstance(cell, Var) or cell is None)
               for row in mtx for cell in row)
assert crossword_typenarrow(CROSSWORD)

# Group the variables into words, horizontally and vertically.
def contig_grps(lst: list[Var | Literal[None]]) -> list[list[Var]]:
    return [cast(list[Var], grp) for grp in (
        list(g) for _, g in groupby(lst, lambda x: x is not None))
            if len(grp) >= MIN_WORD_LEN and grp[0] is not None]
WORDS: list[list[Var]] = list(chain(*(
    [contig_grps(row) for row in CROSSWORD] +
    [contig_grps(col) for col in zip(*CROSSWORD)]
))) # + SPECIALS

##############################################################################
# Main
# ----
#
@APP.command()
def main(
    bidirectional: Annotated[
        bool, typer.Option("--bidirectional", "-b")
    ] = BIDIRECTIONAL
) -> None:
    global ctx
    global BIDIRECTIONAL
    BIDIRECTIONAL = bidirectional  # pyright: ignore[reportConstantRedefinition]

    rich.traceback.install(show_locals=True,
                           width=None,
                           locals_max_length=20)
    
    solver = CrosswordSolver(ctx, WORDS, SPECIALS, BIDIRECTIONAL)
    DBG(solver.wordrels)
    # DBG(solver.get_ctx_repr_for(solver.goal))
    # DBG(CTX(solver.ctx))
    DBG('Unconstrained search space size: '
        f'{humanize.scientific(solver.size(), 2)}')
    
    with rich.live.Live(
        rich.panel.Panel.fit(str(solver),
                             title="Crossword"),
        console=STDERR,
        auto_refresh=False,
        transient=False
    ) as live:

        start_time = time.time()

        def per_sec_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            (seconds_since_last_tick,  # pyright: ignore[reportUnusedVariable]
                cur_time) = data
            live.update(solver.renderable(cur_time - start_time),
                       refresh=True)
            return ctx
        solver.hook_per_sec(per_sec_cb)

        INF('Running the solver.')
        STDERR.rule('Solver Running')
        for solution in solver:
            NOP(solution)
    STDERR.rule('Solver Done')
    INF(f'Last state:\n{solver}')
    INF(f'Number of substitutions: {humanize.intcomma(solver.steps_count)}')
    INF(f'Found {humanize.intcomma(len(solver.seen))} solutions.')


##############################################################################
# Demonstrating a custom solver.
# ------------------------------
#
class CrosswordSolver(Solver):
    # A 2D array of words (as uint8s) per word length.
    a2d_by_len: ClassVar[
        dict[int,
             np.ndarray[tuple[int, int],
                        np.dtype[np.uint8]]]]
    definitions: ClassVar[
        dict[str, set[str]]]
    
    words: list[list[Var]]
    specials: list[list[Var]]
    wordrels: list[FactsTable[np.dtype[np.uint8], Any]]
    subgoals: list[GoalCtxSizedVared]
    progress: rich.progress.Progress | None
    
    seen: set[tuple[str, ...]] = set()
    
    def __new__(cls: type[Self], *args: Any, **kwargs: Any) -> Self:
        self = super().__new__(cls)
        if not self._is_class_init():
            self._class_init()
        return self
    
    @classmethod
    def _is_class_init(cls: type[Self]) -> bool:
        return hasattr(cls, 'a2d_by_len') and hasattr(cls, 'definitions')
    
    @classmethod
    def _class_init(cls: type[Self]) -> None:
        cls.a2d_by_len, cls.definitions = cls.nltk_word_len_to_arr2d()
    
    def __init__(self: Self, ctx: Ctx,
                 words: list[list[Var]],
                 specials: list[list[Var]] | None = None,
                 bidirectional: bool = False,
                 progress: rich.progress.Progress | None = None
    ) -> None:
        self.words = words
        self.specials = specials if specials else []
        self.progress = progress
        self.wordrels = [self.mk_word_rel(i, *word)
                         for i, word in enumerate(words)]
        if bidirectional:
            self.subgoals = []
            for rel, word in zip(self.wordrels, words):
                if any(word == special for special in self.specials):
                    self.subgoals.append(rel(*word))
                else:
                    disj = Or(rel(*word), rel(*word[::-1]))
                    assert isinstance(disj, GoalCtxSizedVared)
                    self.subgoals.append(disj)
        else:
            self.subgoals = [rel(*word)
                             for rel, word in zip(self.wordrels, words)]
        goal = And(*self.subgoals)
        vars = tuple(set(v for word in words for v in word))
        super().__init__(ctx, vars, goal)
    
    @classmethod
    def mk_word_rel(cls: type[Self], n: int, *vars: Var
                    ) -> FactsTable[np.dtype[np.uint8], Any]:
        return FactsTable[np.dtype[np.uint8], Any](
            cls.a2d_by_len[len(vars)],
            name=f'word_{n:02d}')

    def get_word_rel_facts(self: Self, name: str) -> Iterable[str]:
        for rel in self.wordrels:
            if rel.name == name:
                for fact in rel.get_facts():
                    yield fact.tobytes().decode()
    
    @classmethod
    def nltk_word_len_to_arr2d(cls: type[Self]) -> tuple[
        dict[int,
             np.ndarray[tuple[int, int],
                        np.dtype[np.uint8]]],
        dict[str, set[str]]
    ]:
        wordset: dict[str, set[str]]
        try:
            wordset = cls.get_wordset()
        except LookupError:
            INF('NLTK corpus WordNet not found. Downloading.')
            nltk.download('wordnet')  # type: ignore
            wordset = cls.get_wordset()
        INF(f'Got {humanize.intcomma(len(wordset))} words.')

        wordlist_by_len: dict[int,
                              list[np.ndarray[tuple[int],
                                              np.dtype[np.uint8]]]
                              ] = defaultdict(list)
        for word in wordset:
            wordlist_by_len[len(word)].append(
                np.frombuffer(word.encode(), dtype=np.uint8))
        
        arr2d_per_len: dict[int,
                            np.ndarray[tuple[int, int],
                                       np.dtype[np.uint8]]] = {}
        for length, arrlist in wordlist_by_len.items():
            arr2d_per_len[length] = np.stack(arrlist)

        return arr2d_per_len, wordset
    
    @classmethod
    def get_wordset(cls: type[Self]) -> dict[str, set[str]]:
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

    def __solution__(self: Self) -> tuple[Ctx, tuple[str, ...]]:
        """Reconstruct a solutions from a solved context."""
        sol: list[str] = []
        for subgoal in self.subgoals:
            word: list[str] = []
            for var in subgoal.vars:
                val: str | Var
                self.ctx, val = Vars.walk_reify(self.ctx, var)
                if isinstance(val, Var):
                    word = []
                    break
                word.append(val)
            if word:
                sol.append(''.join(word))
        ret = tuple(sol)
        self.seen.add(ret)
        return self.ctx, ret
    
    def repr_latest_solution(self: Self) -> str:
        ctx = self.latest_solution_ctx
        _, ret = self.show(ctx if ctx else NoCtx)
        return ret
    
    def __repr__(self: Self) -> str:
        """Show the solver state."""
        _, ret = self.show(self.ctx)
        return ret
    
    def show(self: Self, ctx: Ctx, internal: bool = False) -> tuple[Ctx, str]:
        lines: list[str] = []
        for row in CROSSWORD:
            show: list[Any] = []
            for cell in row:
                if isinstance(cell, Var):
                    ctx, val = Vars.walk_reify(ctx, cell)
                    show.append(' ')
                    if isinstance(val, Var):
                        show.append('_')
                    else:
                        if not internal and self.specials \
                            and cell in self.specials[
                                int(time.time()) % len(self.specials)]:
                            show.append(f'[bright_cyan][bold]{val}[/bold][/bright_cyan]')
                        else:
                            show.append(val)
                    show.append(' ')
                else:
                    show.append('   ')
            lines.append("".join(str(s) for s in show))
        return ctx, "\n".join([f' {line} ' for line in lines])
    
    def renderable_definitions(self: Self, words: Iterable[str]
                               ) -> rich.table.Table:
        tab = rich.table.Table(
            box=rich.box.SIMPLE_HEAD,
            show_header=False,
            row_styles=['', 'cyan'])
        tab.add_column(justify='center', style='white',
                        vertical='middle')
        if BIDIRECTIONAL:
            tab.add_column(width=2, justify='left', style='white',
                        vertical='middle')
        tab.add_column(width=60, no_wrap=True, style='white',
                    justify='left')
        n, xys = 0, len(WORDS) # - len(SPECIALS)
        for word in words:
            rev = ' '
            n += 1
            if word not in self.definitions:
                rev = '⬅'
                word = word[::-1]
            defs = self.definitions[word]
            if len(defs) > MAX_DEFINITIONS:
                defs = sorted(defs, key=len, reverse=True)[:MAX_DEFINITIONS]
            text: list[str] = []
            for d in defs:
                if n % 2:
                    text.append(f'- {d}')
                else:
                    text.append(f'+ {d}')
            if BIDIRECTIONAL:
                args = (word, rev, '\n'.join(text))
            else:
                args = (word, '\n'.join(text))
            if n == 1 + xys:
                tab.add_row(*((None,)*(len(args)-1)),
                    "Specials:",
                    style='bright_white bold italic underline')

            if SPECIALS and n - xys == 1 + (int(time.time()) % len(SPECIALS)):
                tab.add_row(*args,
                            style='bright_cyan bold')
            else:
                tab.add_row(*args)
        return tab
    
    @rich.console.group()
    def renderable_running(self: Self,
                           elapsed: float | None = None
    ) -> Iterable[rich.console.RenderableType]:
        if not elapsed:
            return
        _, internal = self.show(self.ctx, internal=True)
        yield rich.panel.Panel.fit(
                rich.padding.Padding(f'{internal}', 1),
                title=f"Sub {humanize.intcomma(self.steps_count)}")
        yield rich.panel.Panel.fit(
                rich.padding.Padding(
                    f'{timedelta(seconds=int(elapsed))}', 1),
                title="Running")

    def renderable(self: Self,
                   elapsed: float | None = None
    ) -> rich.console.RenderableType:
        render: list[rich.console.RenderableType] = []
        solution = self.latest_solution()
        if solution:
            sol = f'Solution {humanize.intcomma(len(self.seen))}'
            render.append(
                rich.console.Group(
                rich.panel.Panel.fit(
                    rich.padding.Padding(self.repr_latest_solution(), 1),
                    title=sol),
                self.renderable_running(elapsed)))
            render.append(rich.panel.Panel.fit(
                self.renderable_definitions(solution),
                title=f'{sol} Definitions'))
        else:
            render.append(self.renderable_running(elapsed))
        return rich.columns.Columns(render, align='center')


if __name__ == '__main__':
    APP()

