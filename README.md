# Pyata

Pyata [ˈpʲjɑtɑ] is a general logic solver (or symbolic rule-based inference engine) in Python.  It is based on its own implementation of miniKanren relational programming EDSL (embedded domain specific language).  Pyata is under heavy development, and its API is still very fluid.  Consider it pre-alpha.

![Front](./front.gif)

## Updates

- 2024-02-28: much better conjunction search space prunning by the newly implemented `PositiveCardinalityProduct` constraint

## Features

- The usual miniKanren goodness of:
  - Omnidirectional computation (forward, backward, or fill in the holes)
  - Guaranteed solutions if they exist, even in presence of failing infinite recursive search spaces branches
- `Facets`: Modular, immutable HAMT-based context weaving,
  enabling minimal accidental complexity of extensions
- Support for creating custom hooks for extensions (Events, Broadcasts, Pipelines)
- Performant metrics (counters, gauges, stopwatches), with per-second stats timeseries (can be used for ML search guide)
- Live state observation with [Rich](https://rich.readthedocs.io/) integration
- Custom constraint support, with propagation
- Performant numpy-based facts relations
- Automatic and extensible goal reordering optimizations utilizing goal traits:
  - `Vared`: does the goal keep track of its variables?
  - `CtxSized`: is the goal aware of its search-space size?
- Automatic and extensible search-space pruning

## Running Examples

### Prerequisites
```bash
python3 -m pip install -U poetry
```

### Crosswords
The `crosswords.py` example can be run in docker from project root with:
```bash
make crosswords
```
On MacOS you may need to use `gmake` instead of its ancient `make`.

## Roadmap

### Short-term
- Progress reporting by solvers
  (Connectives are already hooked, just need to write CBs for conjunction and disjunction)
- `Sympy` integration for expressive numeric constraints, and constraints simplification during propagation
  (Var's are already `sympy.Symbol`s, so it's a matter of extending unification and constraints)
- [DONE] ~~More advanced auto-pruning of `Vared` and `CtxSized` goals via goal cardinality constraints
  (needs a way to mark unsafe CBs so they are cleared for such look-ahead types of contexts)~~
- Delegate per-sec stats summarization to hooks for custom modularity
- Extend unification with a unification lattice to reason about type intersections and unions (anti-unification)
- Demo DCG for WASM Sexprs parsing and synthesis
- Abstract and extend FactsTable for additional support of [Polars](https://pola.rs/)
- Add extensive test harness
- Add user and developer documentation

### Short-term Optional
- Pure relational arithmetic (good for problems valuing unconstrained pure relational aspect above performance)
  Can be implemented using `FactsTable`, gaining auto-pruning for free, for arbitrary integer precision arithmetic. Then extended to rationals, and later to contined fractions and more advanced operations as relations
- Pure relational lambda calculus
  - with normalization (required for higher-order unification and optimized implementation synthesis)

### Longer-term
- Even more advanced pruning can be done by introducing a stage running a simpler goal only considering entangled variables of connectives to identify dead branches earlier
- Implement auto-parallelized base solver
- Extend unification lattice with parametric lattice to reason about parametric types
- Write WASM interpreter in Pyata
- Add ML-based search guidance
- Implement implementation inference
- Implement relation inference
- Implement higher-order unification
- Implement a general relation inference
- Port to Mojo for orders of magnitude performance improvement
- Provide Pyata as LLM tool
- Implement distributed base solver

### Ultimate
- Explore non-NN (or hybrid) language model inference
- Explore self-optimizing inference

## Planned Integrations

- [Polars](https://pola.rs/) to use its DataFrame and LazyFrame with its every supported datasource as fact relations
- Z3 SMT solver to speed up many aspects of constraint propagation and search optimization.  It's incremental mode fits Pyata almost as naturally as Sympy does
- TensorFlow and/or PyTorch for ML-based search guidance

## Potential Integrations

- Pyomo for optimization
- SVXPY for convex optimization
- One of topological optimization libraries for experimential search guidance
- PuLP for linear programming, maybe?
- Gurobi for mixed integer programming, maybe?

## Possible Applications

### Immediate (more or less)

- DCG specification for context-aware language grammar, providing at the same time parsing, generation, hole-filling, and with a bit more effort, translation
- Prototyping solvers for any specific problem domain that doesn't have a dedicated solver readily available
- Prototyping new type systems, and programming languages
- [Experimential mathematics](https://en.wikipedia.org/wiki/Experimental_mathematics)

### Non-immediate

- Relational interpreters for existing programming languages, providing cutting-edge type inference, checking, and proving; implementation inference, automatic edge-case detection, test-case generation with edge-case coverage verification, general verification that is certifiable (in a sense of "here are the steps that [dis]prove it")

### Longer-term

- Uptraining existing base LLM model to always use a tool like this for reasoning, making them robust and reasoning transparent

## Screenshots
Example from [./src/python3.12/pyata/examples/crosswords.py](./src/python3.12/pyata/examples/crosswords.py),
demonstrating performance of unification over a large search space.

![Crosswords](./crosswords.png)

Example from [./src/python3.12/pyata/examples/permutations.py](./src/python3.12/pyata/examples/permutations.py),
demonstrating live context observation.

![Permutations](./permutations.png)

