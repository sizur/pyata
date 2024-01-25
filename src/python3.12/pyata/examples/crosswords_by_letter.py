#!/usr/bin/env python3
# -*- coding: utf-8; mode: python -*-

from __future__ import annotations
from typing import Any, Iterable, Self

import nltk           as NL  # pyright: ignore[reportMissingTypeStubs]
import loguru         as LG
import rich.live      as RV
import rich.logging   as RL
import rich.panel     as RP
import rich.pretty    as RY
import rich.traceback as RT
import typer          as TR

from pyata.core import (
    Ctx, NoCtx, Eq, And, Or, Vars, Substitutions, Goal, Var, GoalABC, Stream,
    Solver
)

RT.install()
LG.logger.configure(handlers=[dict(
    level="DEBUG",
    sink=RL.RichHandler(
        markup=True,
        show_path=False,),
    format="{message}",)])

PUZ1 = [
    [ 0, 1, 0],
    [ 1, 1, 1],
    [ 0, 1, 0],
]

PUZ2 = [
    [ 1, 0, 1, 1, 1 ],
    [ 1, 0, 1, 0, 1 ],
    [ 1, 1, 1, 1, 1 ],
    [ 0, 1, 0, 0, 1 ],
    [ 0, 1, 1, 1, 0 ]
]

PUZ3 = [ # --> i -->                    |
    [ 1, 1, 1, 1, 1, 0, 1, 0, 1, 0 ], # V
    [ 1, 0, 1, 0, 1, 0, 1, 1, 1, 1 ], # 
    [ 1, 1, 1, 1, 1, 0, 1, 0, 1, 0 ], # j
    [ 0, 1, 0, 0, 1, 1, 1, 1, 1, 1 ], # 
    [ 1, 1, 1, 1, 0, 0, 0, 1, 1, 1 ], # |
    [ 0, 1, 0, 1, 0, 0, 0, 1, 0, 1 ], # V
    [ 1, 1, 1, 1, 0, 0, 1, 1, 1, 1 ],
    [ 1, 0, 0, 1, 1, 1, 1, 0, 1, 0 ],
    [ 1, 0, 0, 1, 1, 0, 1, 0, 1, 0 ],
    [ 1, 0, 0, 1, 1, 1, 1, 1, 1, 1 ],
    [ 1, 1, 1, 1, 1, 0, 1, 0, 1, 0 ],
]

PUZ = PUZ2


class Word(GoalABC):
    letters: tuple[Var, ...]
    words_list: list[str]
    goal: Goal
    
    def __init__(self: Self,
                 words_list: Iterable[str],
                 *letters: Var
    ) -> None:
        self.letters = letters
        self.words_list = [w for w in words_list if len(w) == len(letters)]
        
        # Construct the goal
        words: list[Goal] = []
        for word in self.words_list:
            a_word: list[Goal] = []
            for letter, char in zip(self.letters, word):
                a_word.append(Eq(letter, ord(char)))
            words.append(And(*a_word))
        self.goal = Or(*words)
    
    def __call__(self: Word, ctx: Ctx) -> Stream:
        return self.goal(ctx)

class CrosswordByLetter(Solver):
    ctx: Ctx
    puzzle: list[list[int]]
    word_set: set[str]
    vars_ij: dict[tuple[int, int], Var]
    word_goals: list[Goal]
    
    def __init__(self: Self,
                 word_set: set[str],
                 puzzle: list[list[int]],
                 ctx: Ctx = NoCtx
    ) -> None:
        self.ctx        = ctx
        self.puzzle     = puzzle
        self.word_set   = word_set
        self.vars_ij    = {}
        self.word_goals = []

        # Rows
        for j, row in enumerate(puzzle):
            in_word: bool = False
            letters_ij: list[tuple[int, int]] = []
            for i, val in enumerate(row):
                if val == 1:
                    if not in_word:
                        in_word = True
                        letters_ij = []
                    letters_ij.append((i, j))
                elif in_word:
                    in_word = False
                    self.ctx, vars_ = Vars.fresh(self.ctx, str, len(letters_ij))
                    for (i, j), var in zip(letters_ij, vars_):
                        self.vars_ij[i, j] = var
                    self.word_goals.append(Word(self.word_set, *vars_))
            if in_word:
                self.ctx, vars_ = Vars.fresh(self.ctx, str, len(letters_ij))
                for (i, j), var in zip(letters_ij, vars_):
                    self.vars_ij[i, j] = var
                self.word_goals.append(Word(self.word_set, *vars_))

        # Columns
        for i in range(len(puzzle[0])):
            in_word: bool = False
            letters_ij: list[tuple[int, int]] = []
            for j in range(len(puzzle)):
                if puzzle[j][i] == 1:
                    if not in_word:
                        in_word = True
                        letters_ij = []
                    letters_ij.append((i, j))
                elif in_word:
                    in_word = False
                    vars: list[Var] = []
                    for coord in letters_ij:
                        if coord in self.vars_ij:
                            vars.append(self.vars_ij[coord])
                        else:
                            self.ctx, (var,) = Vars.fresh(self.ctx, str, 1)
                            self.vars_ij[coord] = var
                            vars.append(var)
                    self.word_goals.append(Word(self.word_set, *vars))
            if in_word:
                vars: list[Var] = []
                for coord in letters_ij:
                    if coord in self.vars_ij:
                        vars.append(self.vars_ij[coord])
                    else:
                        self.ctx, (var,) = Vars.fresh(self.ctx, str, 1)
                        self.vars_ij[coord] = var
                        vars.append(var)
                self.word_goals.append(Word(self.word_set, *vars))
        
        # Well, that was long... All of that was just to have a
        # 1-1 between Vars and 1s in the puzzle.
        # Let's Smoke-test
        assert len(self.vars_ij) == sum(sum(row) for row in puzzle)
        
        self.prep_ctx()
        super().__init__(self.ctx, tuple(self.vars_ij.values()), And(*self.word_goals))

    def __repr__(self: Self) -> str:
        lines: list[str] = []
        ctx = self.ctx
        for j, row in enumerate(self.puzzle):
            show: list[Any] = []
            for i in range(len(row)):
                if (i, j) in self.vars_ij:
                    ctx, val = Substitutions.walk(
                        ctx, self.vars_ij[i, j])
                    if isinstance(val, Var):
                        show.append("⎵")
                    else:
                        show.append(chr(val))
                else:
                    show.append(" ")
            lines.append(" ".join(str(s) for s in show))
        return "\n".join([f' {line} ' for line in lines])


def main() -> None:
    puz = PUZ
    
    LG.logger.info(f'Massaging NTLK corpus: {NL.corpus.words}')
    words = set(word.upper() for word in NL.corpus.words.words())
    
    LG.logger.info(f'Constructing Solver now. (finished {NL.corpus.words})')
    ctx: Ctx = NoCtx
    solver = CrosswordByLetter(words, puz, ctx)
    
    LG.logger.info(f'Running Solver')
    with RV.Live(RP.Panel.fit(str(solver)),
                 auto_refresh=False,
                 transient=True
    ) as live:
        
        def per_sec_cb(ctx: Ctx, data: tuple[int, float]) -> Ctx:
            ctx, vals = Vars.walk_and_classify_vars(
                ctx, solver.vars)
            groud = [val for val in vals if not isinstance(val, Var)]
            LG.logger.info(f'Current ground letters: {len(groud)} / {len(vals)}')
            LG.logger.info(f'Steps taken: {solver.steps_taken()}')
            crossword = RP.Panel.fit(
                str(solver), title="Crossword")
            # state = RP.Panel.fit(
            #     RY.Pretty(CtxRichRepr(ctx)), title="Solver State")
            live.update(crossword, refresh=True)
            return ctx
        solver.hook_per_sec(per_sec_cb)
    
        # Solve
        for solution in solver:
            break
        
    LG.logger.info(f'First Solution:\n{str(solver)}')

TR.run(main)

