
# Ideas

Before elaborating on existing ideas, try to empty the [Inbox](#Inbox) section,
where new ideas are captured as soon as they come to mind.

## Inbox

Capture ideas in here as soon as they come to mind.  Categorize/define them later.

 - Integration hooks to yield for event loops.
 - `Stream` subtypes are search heuristics.
 - `GoalMaker`s (Parametric `Problem`s or `Relation`s) may be `CtxRichReprable`
   to represent current state of the solution search.
    - Further subtypes of that may have default `rich.repr` of showing
      `rich.progress` based on ground/total goal variables.
 - `GoalMaker`s may have other representations, not just `rich.repr`.
    - GUI representations may be interactable, and may inject new constraints
      in the middle of the search — a live human-directed search constraining.
 - `GoalMaker`s may have `sharedmem`/`mmap` representations of current state
   of their parameters to minimize performance impact of the search and
   responsiveness of the GUI.
 - Unification-hooking `Substitutions`+`Constraints` memoization `Facet`.
   This facet will need to contain own state, like [Metrics](src/python/pyata/types/_3_12.py#Facet).
   - ``if Unifications.Failed:`` add to Bloom-filter
   - ``if context :`` add to Map


## 