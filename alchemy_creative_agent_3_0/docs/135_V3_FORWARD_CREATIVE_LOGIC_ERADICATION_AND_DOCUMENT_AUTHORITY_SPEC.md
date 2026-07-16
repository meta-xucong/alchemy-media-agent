# 135 V3 Forward Creative-Logic Eradication And Document Authority Spec

Status: **active, cross-cutting architecture authority.** This document and
Docs134/136 define how V3 distinguishes legitimate deterministic contracts from the
rejected “structured word-stack” creative route. Where an earlier document
describes local prompt fragments, keyword classifications, static image recipes
or retry prose as renderer input, that description is historical only.

## 1. Non-negotiable rule

For every new V3 image operation, regardless of template or whether the image
will be rendered by the Web Provider or relayed to Codex Native ImageGen, the
only renderer-facing creative language is the exact canonical prompt approved
by the remote Central Brain.

```text
protected user intent + admitted reference truth + factual/policy constraints
-> remote Brain reasoning
-> remote Brain final validation and one canonical prompt per frozen output
-> Provider or Local MCP relays that exact normalized string and hash
```

No local stage may add, remove, reorder, deduplicate, translate or “repair”
creative words after that sign-off. A missing, unapproved or wrong-cardinality
sign-off is a terminal blocked state, not permission to revive a local
assembler.

## 2. The rejected route

The following are expressly prohibited as forward creative decision-makers or
renderer language for a new V3 Job:

- raw keyword, regex or substring detection used to decide a subject’s medium,
  age, realism, beauty, commercial genre, camera, composition or delivery
  meaning;
- local `prompt_additions`, negative-word piles, prompt deduplication,
  phrase-ranked recipes, camera/crop/lighting lists or category-specific
  prompt templates;
- static suite roles, marketplace slots, product boxes, default sales copy or
  scene/camera recipes treated as image instructions;
- review issue code -> local repair sentence / negative list / face-mask edit
  / local re-prompt translation;
- deterministic text overlay, font, OCR-fix, coordinate or canvas route;
- a fallback model or a Local MCP caller authoring an alternative creative
  prompt when the Brain sign-off is absent.

An otherwise harmless phrase such as `cartoon`, `girl`, `Amazon`, a filename
or a review code has no renderer meaning by itself. It may be preserved as
evidence for the Brain to interpret in context. For example, an illustrated
print on a real garment does not make the whole image an illustration.

## 3. What remains deterministic

Deterministic code is still essential, but its authority is bounded to facts,
integrity and safety. It may:

- validate API shape, image size, exact output count and provider capability;
- admit/reject reference files by technical format, integrity hash and declared
  channel;
- freeze template ownership, output ordinal, immutable profile binding,
  activation envelope and lineage;
- enforce hard policy blocks and explicit user constraints without inventing
  an image treatment;
- classify a Provider result as success, empty, timeout, rejection or unknown;
- normalize review observations into opaque/reason-coded evidence;
- retain append-only history, output hashes and safe provenance.

It may not convert those facts into the final wording delivered to an image
model. The Brain owns that conversion and validates the completed wording.

## 4. Audited forward path

| Surface | Required behavior | Rejected behavior |
| --- | --- | --- |
| `LLMBrainAdapter` | Returns remote semantic decision, exact-count direction plan and final approved canonical prompts. | Local fallback or partial remote response becoming a usable creative plan. |
| `CentralCreativeBrain` | Uses a neutral compatibility pack for a Brain-signed enforced execution; a specialized Scenario Pack remains only as a frozen structural contract. | Letting a keyword-selected legacy vertical pack rewrite a Brain-owned brief, layout, prompt shadow or renderer direction. |
| `ScenarioRuntime` | Freezes intent/envelope/ledger, passes the Brain’s own direction plus facts and review evidence to `provider_prompt_finalize`. | Rebuilding a creative brief from capability fragments, static roles or retry prose. |
| `PromptCompilerAgent` | Produces only a non-creative compatibility shadow when a canonical Brain prompt exists. | Generating a second visual prompt, negatives or hard-constraint word stack for a signed Job. |
| `ProductionImageGenerationProvider` | Relays the signed canonical text; every normalized real-image materialization and every actual Provider operation fails closed when that sign-off is absent. | Appending Human Realism, reference, role, retry or recipe text after sign-off. |
| `V3ProductApiService` retry | Forwards normalized issue codes and bounded retry provenance to the next Brain sign-off. | Translating issue codes or ledger templates into local repair language. |
| Human Realism | Executes frozen, Brain-owned rendering semantics; contributes its typed semantic contract to Brain sign-off and contributes evidence/review obligations. | Inferring whole-image stylization from a raw word, emitting a second Provider prompt, or retaining the semantic contract only as an unreachable ledger field. |
| Codex Native MCP | Projects the same canonical string, reference paths and hash as the Web Provider; it creates no Web candidate/delivery. | Replanning, paraphrasing, prompt authoring, Provider fallback or persistence. |

Reference-file admission is equally non-creative.  The frozen Reference
Channel Policy, not an adapter-specific fallback, decides whether a source
frame contributes product facts only or also contributes scene/light/camera
context. Every ingress must first project its caller-declared uploaded assets
into the frozen reference snapshot, so Project Mode, direct API and Codex
relay resolve the same source binding. A product/appearance truth input whose source-frame context is not
explicitly assigned must project the same focused provider derivative to Web
and Codex Native execution; the original upload stays in history but is not
silently reintroduced as a renderer input.  This protects Brain-owned scene
direction without describing a visual treatment locally.

An actual Provider operation has no unsigned escape hatch: its final prompt
must carry the remote Brain's approved canonical provenance. Older local
materialization code may remain readable only for historical diagnostics and
unit fixtures, but it cannot select a Provider, start an upstream request, or
produce a candidate. Normalized real-image materialization also blocks before
returning an unsigned prompt. A signed prompt that exceeds a declared
transport limit is blocked rather than locally compacted or rewritten.

## 5. Compatibility quarantine

Some source files still retain historical data shapes such as
`prompt_additions`, local retry templates, keyword utilities, old role records
and legacy prompt compilation. They are not current creative capabilities.
Their only permitted status is all of the following:

1. read compatibility for archived objects, diagnostics or old tests;
2. no new V3 create/generate path writes the enabling compatibility marker;
3. no normalized enforced Job, Brain-signed Job, Provider materialization or
   Local MCP relay reads them as creative language;
4. a compatibility record is never silently upgraded into a new real-image
   request; a new continuation must re-enter the current Brain-owned path.

In particular, local visual retry phrase catalogs are quarantined behind the
explicit `legacy_prompt_compatibility_record` archival marker. No current V3
create/generate request writes that marker. It is not an API feature, a retry
fallback or an authorized production path.

## 6. Document authority and supersession map

The documentation set is historical by design; old specifications are retained
for traceability. They must be read through this map rather than cherry-picked
as independent implementation authority.

| Document family | Current reading rule |
| --- | --- |
| Docs 76, 91–96, 101–102, 113–115, 117, 124, 127–128 | Their facts, governance, evidence, activation and review principles remain valid only within the Brain-owned final-prompt boundary. They do not authorize local creative phrase emission. |
| Doc111 | Provider-native complete image and no local text-pixel composition remain authoritative. A review failure becomes a Brain/provider-native revision, never an overlay or local word patch. |
| Docs 129–130, 132–133 | Local MCP must preserve exact canonical Provider prompt/reference parity. Doc129’s former Codex-authored creative direction is historical; Doc130/133 parity is authoritative. |
| Docs 48, 50, 52–60, 84 | Earlier planning, visual-cluster, suite/mode, retry and structured-appearance wording is retained as historical contract context. Any local prompt atoms, static roles, recipe or retry-patch renderer semantics are superseded by Docs 111, 113, 134 and 135. |
| Docs 03, 08–09, 18–19, 25, 29–30, 41–42 | Early pipeline, preset, keyword-map, slot and implementation-audit material is historical. It can guide regression coverage only after its local-creative instructions have been ignored; it cannot become a forward rendering authority. |
| Docs 104–110 | Their old text-pixel, copy-plan and slot material is read-compatible only as already marked by Doc111. Doc105's historical continuation route remains available only with an opaque frozen deliverable binding; it must not return as a semantic slot, local rendering path or local creative instruction. |
| E-Commerce E17+ and Photography P11+ | Specialized templates contribute verified facts, structural count/lineage and immutable bindings. They do not supply local whole-image language; the remote Brain supplies it. |

Root Rules (`00_ROOT_RULES.md`) and the specific high-risk historical documents
listed above carry a pointer to this authority. A future document that proposes
local creative wording, a prompt patch, a recipe or a keyword-derived semantic
decision is invalid unless it is explicitly a compatibility/read-only record
and proves it is unreachable from the forward path.

## 7. Mandatory regression evidence

Every change touching generation, review, template planning, reference handling
or Local MCP must prove at least:

1. exact canonical Brain prompt/cardinality reaches Provider and Local MCP with
   the same hash;
2. absent/invalid Brain sign-off blocks before image generation;
3. an object-surface illustration term cannot disable a frozen real-person
   Human Realism execution;
4. a review retry exposes normalized evidence only; forged or local
   `prompt_additions` never reach the finalizer or Provider;
5. a signed Job’s legacy PromptCompilation is an explicitly non-creative
   shadow, not a second final prompt;
6. General, E-Commerce and Photography remain isolated; no static role/slot or
   specialty recipe leaks into another template’s Brain input or Provider text;
7. source scans flag any new Provider-facing use of local prompt fragments,
   retry patch language or keyword-derived creative semantics for review.

## 8. Acceptance conclusion

This is not a ban on contracts or data modeling. It is a ban on pretending that
a catalog of local fragments can replace creative reasoning. V3 should use
structured data to protect truth and govern execution, then require the Brain
to reason over that truth and approve the one complete natural-language image
instruction.
