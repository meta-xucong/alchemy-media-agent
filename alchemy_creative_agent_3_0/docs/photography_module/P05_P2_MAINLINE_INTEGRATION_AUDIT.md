# Photography P2 Mainline Integration Audit

## 1. Status

```text
phase: P2 mainline integration audit
status: shadow-runtime implemented and verified; production activation still blocked by shared hooks
date: 2026-07-12
branch: codex/photography-module
```

P2 confirms that the next safe Photography work can continue as module-owned
planning code imported directly by focused tests. This path can build
Photography briefs, General Photography profile bindings, technique
contributions, shot specs and metadata review profiles without changing shared
public contracts or production behavior.

## 2. Existing Extension Points That Are Sufficient For P3 Shadow Work

The current mainline is sufficient for an inactive, module-local P3 shadow
runtime because Photography can reuse:

```text
V3BaseModel
CapabilityContribution
stable_id
ScenarioPack manifest contracts
module-local Scenario Pack imports
module-local tests
```

This does not authorize production registration. The shadow planner remains
absent from the default Scenario Pack registry, shared frontend shell, Central
Brain route, persistence schema and provider path.

## 3. Shared Hooks Required Before Production Activation

The following mainline needs remain outside Photography-owned implementation:

```text
trusted frontend photographer_profile_id and selection_source fields
catalog list/read endpoint or product contract
job/project persistence for pinned PhotographerProfileBinding
scenario card and shared shell registration hook
photography_template capability policy lookup
global capability catalog compatibility for photography_template
review issue ownership registration for Photography issue families
production result surface fields for final-only delivery plus folded workflow details
```

These cannot be implemented in the Photography branch by changing shared public
contracts, shared registries, frontend shell, Central Brain, provider routing or
global persistence. When a dependent production phase begins, create a
`PX_MAINLINE_REQUEST_<short_name>.md` document for the exact hook and pause that
dependent work.

## 4. P3 Boundary Decision

P3 may proceed only as:

```text
module-owned
planning-only
General Photography default
no named-profile activation
no provider call
no shared registry registration
no public API change
no persistence schema change
```

The P3 shadow planner must block explicitly selected named profiles instead of
silently falling back, because P3 is General-only. Free-text photographer names
and LLM profile suggestions remain non-authoritative and must not change the
profile binding.

## 5. P3 Verification Result

The supervisor sandbox could not execute Python, so verification was completed
from the owning Photography worktree before publication.

```text
Photography P1/P3 focused tests: 19 passed
Scenario Pack / vertical / E-Commerce regressions: 29 passed
full V3 test suite: 538 passed
compile and diff checks: passed
```

Audit-driven repairs completed before acceptance:

1. Keyword detection now uses token boundaries, so `surface` no longer activates
   the portrait `face` signal.
2. Unknown tasks use a neutral `general` scene instead of silently activating
   portrait or animal grammar.
3. Negative constraints are scene-owned and no longer inject face, animal and
   object rules into every Photography job.
4. `prompt_owned` reference channels are allowed changes, never immutable
   reference truth.
5. Human Realism relevance is true only for portrait evidence in the P3 shadow
   contribution; landscape, still-life, animal and general jobs remain isolated.

P3 remains planning-only and unregistered after these checks.
