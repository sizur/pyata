# Pyata

Pyata [ˈpʲjɑtɑ] is a general logic solver (or symbolic rule-based inference engine) in Python.  It is based on its own implementation of miniKanren relational programming EDSL (embedded domain specific language).  Pyata is under heavy development, and its API is still very fluid.  Consider it pre-alpha.

![Front](./front.gif)

## Updates

- 2024-03-08: major auto-pruning improvements, finding solutions of the crosswords example in a few minutes, configured within search space as high as $8.50\times10^{135}$
- 2024-02-28: much better conjunction search space prunning by the newly implemented `PositiveCardinalityProduct` constraint if conjunction contains some `GoalCtxSizedVared` goals

## Motivation

Relational logic solver implementations are notoriously complex.  This often makes prototyping new ideas in the field of symbolic reasoning, and especially in the field of relational programming, a daunting and prohibitive task.  Good progress has been made by globally constraining the general solvers into Datalog or SMTs.  But little progress has been made to bring these benefits back to the fully general solvers, like miniKanren.

Pyata aims to provide a modular, performant, and observable implementation with high degree of orthoginality to facilitate rapid prototyping of underexplored but ripe areas in general relational and symbolic reasoning engines.

## Features

- The usual miniKanren goodness of:
  - Omnidirectional computation (forward, backward, or fill in the holes)
  - Guaranteed solutions if they exist, even in presence of failing infinite recursive search spaces branches
- `Facets`: Modular, immutable HAMT-based context weaving,
  enabling minimal accidental complexity of extensions
- Support for creating custom hooks for extensions (Events, Broadcasts, Pipelines) <br />
  While extensive use of hooks is often discouraged, the gain in orthogonality for a problem of such a high inherent complexity is critical for Pyata, as it is designed to be a platform for new ideas exploration
- Performant metrics (Counters, Gauges, Stopwatches), with per-second stats timeseries (can be used for ML search guide and more advanced heuristics)
- Live state observation with [Rich](https://rich.readthedocs.io/) integration
- Custom constraint support, with propagation
- Performant numpy-based facts relations
- Automatic and extensible goal reordering optimizations utilizing goal traits:
  - `Vared`: does the goal keep track of its variables?
  - `CtxSized`: is the goal aware of its search-space size?
- Automatic and extensible search-space pruning
 
### Implemented heuristics:

- `HeurConjRelevance`: compute and prepend a new relevance goal to conjunctions that solves for unique subfacts (relevant to shared variables) per conjunction goal
- `HeurConjChainVars`: Reorder conjunction goals to minimize search space based on size and (parametric) entanglement factor (computed from shared variables), while trying to chain goals with shared variables as much as possible, so conflicts are encountered earlier
- `HeurConjCardinaliry`: Add cardinality constraints to conjunction goals to auto-prune search space, where possible
- `HeurFactsOrdRnd`: Randomize facts enumeration order

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
- Implement a facts ordering heuristic minimizing connective cardinality
- Progress reporting by solvers
  (Connectives are already hooked, just need to write CBs for conjunction and disjunction)
- `Sympy` integration for expressive numeric constraints, and constraints simplification during propagation
  (Var's are already `sympy.Symbol`s, so it's a matter of extending unification and constraints)
- [DONE] ~~More advanced auto-pruning of `Vared` and `CtxSized` goals via goal cardinality constraints
  (needs a way to mark unsafe CBs so they are cleared for such look-ahead types of contexts)~~
- Improve `HeurConjCardinality` to apply constraints only to relevant (entangled) variables
- Parameterize `HeurConjRelenvance` to optionally pre-solve the relevance goal, and how (should that use hypothetics or use a fresh solver, and with what extensions)
- Parameterize `HeurConjChainVars` to optionally use a different entanglement factor, and how chaining should (or not) be done
- Delegate per-sec stats summarization to hooks for custom modularity
- Extend unification with a unification lattice to reason about type intersections and unions (anti-unification)
- Demo DCG for [WASM Sexprs](https://webassembly.github.io/spec/core/text/index.html) parsing and synthesis
- Abstract and extend FactsTable for additional support of [Polars](https://pola.rs/)
- Add extensive test harness
- Add user and developer documentation
- Add DCG for Datalog/Prolog for existing knowledgebase ingestion
- Add context serialization/deserialization
- And periodic context refresh as workaround for immutable HAMT compaction ("garbage-day") <br />
  While immutable HAMT makes context accounting and backtracking easy, `immutables` library does not perform compaction, so performance and memory usage still degrades over time, as context modifications that went out of scope and became unreachable, still accumulate in the HAMT structure.  This is a known issue, and the workaround is to periodically serialize and deserialize the context, or just perform a deep copy.

### Short-term Optional
- [HALF-DONE] Pure relational arithmetic (good for problems valuing unconstrained pure relational aspect above performance)
  Can be implemented using `FactsTable`, gaining auto-pruning for free, for arbitrary integer precision arithmetic. Then extended to rationals, and later to contined fractions and more advanced operations as relations
- Pure relational lambda calculus
  - with normalization (required for higher-order unification and optimized implementation synthesis)

### Longer-term
- [Done] ~~Implement more advanced pruning can be done by introducing a stage running a simpler goal only considering entangled variables of connectives to identify dead branches earlier~~
- Add a goal executions facet used for lazy goal binding, enabling better heuristics during connective goal execution
- Explore storing fact relations as fully auto-normalized id-value maps,
  eliminating tradeoff between forward and backward inference chaining,
  and naturally supporting hypothetical reasoning (new facts become a part of backtrackable context),
  and enabling better heuristics through better visibility of relational attribute domains
- Implement probabilistic reasoning
- Add support for ordered goal trait to use order constraints for binary search over ordered relations
- Switch to a Rust-based implementation of concurrency-supported immutable HAMT, ideally that also support compaction
- Implement auto-parallelized base solver
- Extend unification lattice with parametric lattice to reason about parametric types
- Write WASM interpreter in Pyata
- Write x86_64 interpreter (common instruction subset) in Pyata
  for reverse engineering, verification, optimization, and synthesis of binaries
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

