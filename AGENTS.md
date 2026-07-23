# AlchemyOS Agent Development Principles

## Parallel Development and Main Integration Policy

This repository uses Git worktrees for concurrent development. Treat the
`main` branch as the stable integration line and assign it a single active
writer at a time.

Roles:

1. The mainline integrator owns the current `main` checkout and is the only
   agent allowed to make direct feature commits to `main`.
2. Parallel feature work must use its own worktree and its own feature branch.
   A parallel agent must never develop directly on `main` or reuse the
   mainline integrator's working directory.
3. The branch used by one active worktree must not be checked out for editing
   in another worktree.

Mainline integrator rules:

1. Before starting a task, inspect `git status` and synchronize with
   `origin/main` when it can be fast-forwarded safely.
2. At every small, independently verifiable milestone: run the relevant tests,
   review the diff for unrelated files and temporary artifacts, commit the
   change, and push it to `origin/main`.
3. Keep `main` runnable and avoid leaving completed foundation work only as
   uncommitted local changes.
4. Do not create, switch to, reset, clean, delete, or otherwise alter another
   active worktree or its feature branch.

Parallel feature rules:

1. Create the feature worktree from the current `origin/main`, use a clearly
   scoped branch name, and confine changes to the assigned subsystem whenever
   possible.
2. Before beginning a new milestone and again before integration, fetch and
   rebase the feature branch onto the latest `origin/main`.
3. Run feature-relevant tests before requesting integration. Resolve conflicts
   on the feature branch, then merge only after the resulting integrated state
   is verified.
4. Coordinate before changing shared contracts: request/response schemas,
   generation routing, public component interfaces, shared dependencies, lock
   files, or cross-cutting documentation.

Safety rules:

1. Never use destructive Git commands such as `git reset --hard`, `git clean`,
   or a file-overwriting checkout unless the user explicitly authorizes that
   exact operation.
2. Do not commit logs, caches, evaluation scratch directories, generated
   contact sheets, or other temporary artifacts unless they are intentional
   repository assets.
3. Completion reports must state: affected scope, tests run and results,
   commit hash, push status, and any remaining integration dependency.

Short form:

```text
One writer owns main.
Each parallel task owns one worktree and one branch.
Sync early, test before integrating, and protect other worktrees.
```

## Theory-First Correction Principle

When a development task produces behavior that differs from the expected
outcome, or when a test or real validation run fails, do not immediately stack
local patches and rerun the same test loop.

Before changing code, first write down the correction model:

1. State the intended behavior and the exact observed mismatch.
2. Identify the responsible layer: product contract, shared runtime, Brain
   prompt contract, Provider/MCP outlet, Vision/review gate, persistence,
   public projection, or frontend interaction.
3. Check whether existing rules conflict, duplicate each other, or apply at the
   wrong layer.
4. Decide which rule remains authoritative, which rule is only supporting
   evidence, and which older wording must be superseded or narrowed.
5. Define the minimal complete fix that should pass in theory before touching
   code.
6. Only then implement, add or update regression tests, run the relevant test
   set, and proceed to real validation.

Do not treat repeated prompt tweaks, threshold nudges, or one-off validation
scripts as a substitute for the theory pass.  If the failure suggests the
current direction is wrong, pause implementation and re-evaluate the model
instead of continuing the patch/test spiral.

Short form:

```text
Think the system through first.
Then patch once at the right layer.
Then test.
```

## Workspace Encoding Rules

- Treat all source, config, markdown, JSON, YAML, CSV, and text files as UTF-8 unless a file clearly uses another encoding.
- When reading or writing text in PowerShell, prefer explicit UTF-8 encoding options such as `-Encoding utf8`.
- Before running commands that pipe or display Chinese text in PowerShell, ensure the session uses UTF-8:
  `[Console]::InputEncoding = [System.Text.UTF8Encoding]::new(); [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $OutputEncoding = [System.Text.UTF8Encoding]::new(); chcp 65001 > $null`
- Do not put Chinese literals directly inside `shell_command` command strings. If a command must create or compare Chinese text, put the text in a UTF-8 file, use `apply_patch`, or construct it with Unicode escapes.
- For Python scripts, open files with `encoding="utf-8"` when reading or writing text.
- Avoid ad hoc byte/string conversions for Chinese text; use structured parsers and explicit encodings.

## V3 Foundation vs Specialized Template Principle

When developing Alchemy Media Agent V3, always follow:

```text
Foundation makes every image better.
General Template stays simple and scenario-neutral.
Specialized templates decide what a professional set should contain.
```

Detailed authority:

```text
alchemy_creative_agent_3_0/docs/76_V3_FOUNDATION_VS_SPECIALIZED_TEMPLATE_GOVERNANCE_SPEC.md
alchemy_creative_agent_3_0/docs/77_V3_REAL_VISUAL_REVIEW_AND_AESTHETIC_STABILITY_FOUNDATION_SPEC.md
alchemy_creative_agent_3_0/docs/78_V3_LONG_TERM_IDENTITY_AND_BEAUTIFUL_REALISM_FINAL_TUNING_SPEC.md
alchemy_creative_agent_3_0/docs/93_V3_REFERENCE_CHANNEL_POLICY_AND_PROMPT_OWNERSHIP_GOVERNANCE_SPEC.md
alchemy_creative_agent_3_0/docs/94_V3_UNIVERSAL_VISUAL_CAPABILITY_DEOVERFITTING_AND_GOVERNANCE_SPEC.md
alchemy_creative_agent_3_0/docs/95_V3_UNIVERSAL_PORTRAIT_IDENTITY_EVIDENCE_AND_BEST_RESULT_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/96_V3_HIGH_FIDELITY_PORTRAIT_IDENTITY_METRIC_AND_LOCAL_REPAIR_SPEC.md
```

Hard rules:

1. Universal capabilities such as single-image aesthetics, identity/product/style consistency primitives, photorealism, anti-AI-feel, automatic curation, generated-image visual review, bounded retry, watermark/text/artifact detection, prompt refinement, and selected-result continuity belong in the V3 foundation quality layer.
2. The General Template must remain beginner-friendly and scenario-neutral. It can support simple modes such as similar alternatives, basic suite expansion, creative exploration, and format/layout adaptation, but it must not become an ecommerce, photography, brand-kit, storyboard, or campaign-package builder.
3. Specialized templates own scenario-specific deliverable maps and packaging. E-Commerce owns listing/A+ product image roles. Photography owns portrait/session roles. Brand owns brand-kit assets. New Media owns platform/content deliverables.
4. If a feature defines what images a professional scenario should output, put it in that specialized template, not in General Template or the shared Visual Capability Cluster.
5. If a feature improves quality for almost every image, implement it as a reusable V3 foundation capability under the shared capability / brain / provider / review layers.
6. If the correct output package depends on a hidden use case the user did not state, do not hard-code the assumption into General Template. Keep General neutral or expose a simple user choice.
7. Before changing V3 visual generation, state whether the work is foundation, General Template, or specialized template work, and add tests proving it does not leak into the wrong layer.
8. Real visual review and aesthetic stability tuning must extend the V3 foundation review/provider/retry paths; it must not create vertical deliverable maps inside General Template.
9. Long-term human identity and beautiful realism tuning must preserve attractive facial-feature design, including eyes, brows, nose-mouth relationship, jaw/chin direction, skin/lighting realism, and natural variation; never make a face less beautiful merely to make it look realistic.
10. Retry outputs are append-only internally, but beginner-facing V3 result surfaces must show only final delivery outputs up to the requested count; retry-superseded originals belong in folded workflow/history details.
11. When an uploaded portrait is used as a same-person reference, identity-critical traits from the image override conflicting prompt aesthetics unless the user explicitly asks to redesign or change the person.
12. Doc91 Human Realism Plugin is a shared Visual Capability Cluster plugin. Any V3 path that generates real people, models, visible faces, hands, skin, product-on-person, fashion, kidswear, or lifestyle scenes with people must route anti-AI-face and real-camera human guidance through that plugin, even when the template subject is product. Do not duplicate this logic inside General, E-Commerce, Photography, or Central Brain code.
13. Child, teen, or kidswear realism rules are only auxiliary branches inside the general Human Realism Plugin. They may strengthen age-appropriate realism when detected, but they must never turn the shared module into a child-specific or kidswear-specific solution.
14. Doc92 Human Realism must be style-aware. Do not push bright/fresh/luminous/high-key/bounce-light commercial skin language into moody, dark, ancient/traditional, cinematic, low-key, or melancholic portraits. In those cases, reduce AI-feel through real texture, controlled highlights, soft-matte skin, lens realism, and anti-plastic negatives while preserving the requested mood.
15. Doc93 is the current reference-inheritance authority. An ordinary uploaded portrait is identity truth by default: strongly preserve bone structure and facial-feature relationships, but keep hair styling, makeup, wardrobe, lighting, color, scene, camera, mood, and whole-image style owned by the current prompt unless the user explicitly assigns or locks those channels. `preserve_person_identity` must never silently become a hair, outfit, lighting, scene, or style lock. Human Realism may improve rendering quality but must not expand reference inheritance rights.
16. Doc94 is the shared-runtime anti-overfitting authority. Historical ancient-style, kidswear, East Asian summer, marketplace, costume, or other narrow cases may be regression fixtures, but must not become named branches or default prompt recipes in the shared Visual Capability Cluster, provider materializer, General Template, or Central Brain. Shared runtime rules must use orthogonal visual variables such as identity geometry, age fidelity, exposure key, skin specularity, texture, complexion preservation, and prompt-owned channels.
17. A new shared visual rule must prove usefulness across at least three materially different scenes. Scene-specific deliverable or art-direction logic belongs in a specialized template. Compatibility aliases may read old metadata but must not continue emitting superseded narrow prompt fragments.
18. Doc95 is the current same-person evidence authority. Identity-only portrait references use complementary feature-detail and head-geometry evidence, keep full source frames suppressed unless Doc93 assigns another source-owned channel, preserve the full identity-critical feature contract inside prompt budgets, and compare retry attempts rather than assuming the newest retry is best.
19. Doc96 is the current high-fidelity identity execution authority. Hard portrait/product truth requests must capability-negotiate high input fidelity, portrait identity may be evaluated with ephemeral local metrics that are never persisted as biometric vectors, and identity-only failures should use one bounded face-local repair when the rest of the image is already correct. Full user prompts remain lossless; only duplicated framework guidance may be compacted.

Short form:

```text
Quality is shared.
Professional deliverables are template-specific.
General Template is not the place for every vertical's suite director.
```

## Specialized Module Documentation Isolation Rule

When preparing or implementing a V3 professional module such as E-Commerce,
Photography, Brand, or New Media:

1. Use a dedicated feature branch and isolated worktree based on the latest
   `origin/main`.
2. Store the module's planning, contracts, roadmap, UI, test, and acceptance
   documents under a module-specific directory with an independent document
   number family, such as `docs/ecommerce_module/E00...`.
3. Treat the module document index as the preparation authority for that module;
   it must identify upstream foundation authorities and explicit conflicts.
4. Do not modify General Template, Central Brain, shared capability behavior,
   provider behavior, or public contracts from a module document-only milestone.
5. If a shared contract or public interface must change, record the compatibility
   impact, migration path, and isolation tests before implementation.
6. A professional module may become active only after its own document family,
   focused tests, UI acceptance, real-output review, and template activation
   gate pass.
7. Platform and category policies must be versioned data/configuration with
   source and review metadata; they must not be treated as permanent universal
   visual rules.
8. General Template may support light product-related imagery, but must not load
   the specialized module's suite roles, platform rules, or export package.

Short form:

```text
One professional module, one isolated branch/worktree, one document family,
one activation gate; shared quality stays shared and General stays neutral.
```

## V2 Template Lock Principle

When developing Custom Media Agent 2.0, preserve this rule:

```text
Selected case first. Uploaded assets fit into the selected case.
```

For V2 image generation:

1. If `template_case_id` is set, the selected case is the highest-priority visual anchor.
2. Claude Code is the central creative orchestrator, but it must not override the selected case's priority.
3. Uploaded images are evidence and template-slot variables. They may replace subject identity, product appearance, logo, face, copy content, or minor props.
4. Uploaded images must not override the selected case's composition, layout, lighting, background density, spatial hierarchy, mood, or overall visual rhythm unless the user explicitly unlocks the template.
5. If no case is selected, Claude Code may freely combine uploaded images with retrieved cases.
6. Hard visual constraints such as product appearance, logo, face, or required background must be passed to capable image providers as input images, not reduced to text-only prompts.
7. Final prompts must not leak internal `case_id`, `asset_id`, `provider_id`, `source_url`, API, repository, or storage identifiers.

Short form:

```text
Selected template controls the frame.
Uploaded assets fill the frame.
Claude decides how to fit them together without breaking the frame.
```

## V2 Uploaded Asset Intent Principle

When Custom Media Agent 2.0 receives uploaded images, every uploaded asset must be interpreted as a concrete fusion intent before prompt composition.

Hard rules:

1. `role` alone is not enough. V2 must derive `fusion_mode`, `placement_intent`, `target_surface`, provider input requirements, and review expectations from the user prompt, asset notes, and asset brief.
2. Hard identity assets such as subject, product, logo, face, and required background must stay as V2-native provider `input_images` whenever the provider supports them.
3. A selected template remains the highest-priority frame. Uploaded assets may fill replaceable slots, but must not override locked template structure.
4. Logo usage must distinguish product or scene surface placement from poster brand mark placement. A logo requested on clothing, packaging, a bottle, a device, a sign, or another scene object must not be treated as a generic corner badge.
5. Claude Code may improve the creative prompt, but it must obey the structured fusion policy and must not erase uploaded-asset intent.

Short form:

```text
Role identifies the material.
Fusion policy identifies what to do with it.
Claude improves the result without changing that intent.
```

## V2 Strict Isolation Principle

When developing Custom Media Agent 2.0, treat V1 and V2 as separate backend products that only share the browser shell and visual style.

Hard rules:

1. V2 backend code must not call `/api/v1/*` or `/v1/*`.
2. V2 backend code must not import modules from `custom_media_agent_docs/src_skeleton/app`.
3. V2 must not read or write V1 `.media_storage`, V1 history, V1 generated images, V1 assets, V1 queues, or V1 runtime provider settings.
4. V2 image generation must use V2-native providers, V2-native storage, V2-native history, and V2-native review.
5. `legacy_image_bridge` is an architecture debt, not an acceptable default or fallback path.
6. Hard visual constraints such as product appearance, logo, face, or required background must remain V2-native `input_images` or V2-native deterministic postprocess steps. They must not be translated into V1 asset roles.

Short form:

```text
V2 may learn from V1, but V2 must not depend on V1.
```

## V2 Claude Continuation Principle

When developing Custom Media Agent 2.0, Claude Code remains the central creative brain even when the upstream route is slow, near an output cap, or close to a context/response limit.

Hard rules:

1. `claude_timeout`, output-token-limit, structured-output exhaustion, or upstream context cancellation must not silently bypass Claude and continue with a deterministic-only creative decision.
2. V2 must use a soft stage boundary before the hard timeout/context/output boundary. When a normal stage approaches that soft boundary without valid compact JSON, the controller must compress state and continue through a shorter Claude micro or ultra-micro stage.
3. If any Claude checkpoint has completed, V2 must preserve that checkpoint, compress the visible state, and continue with a shorter Claude stage or a checkpoint-derived compressed decision.
4. Timeout guards are allowed only as internal boundary triggers for compression and continuation. They are not an acceptable final creative fallback once Claude has started reasoning.
5. Claude may think fully inside each bounded stage, but visible output must always be compact, schema-shaped, and capped by configured prompt/negative/rationale budgets.
6. If Claude is required and no recoverable Claude checkpoint or Claude decision can be produced, V2 must stop the run as failed rather than generate from a deterministic-only creative fallback.
7. Final prompts must come from Claude output or from compressed Claude checkpoints. Local deterministic logic may provide safety scaffolding, provider parameters, and hard guards, but must not replace Claude's creative role.

Short form:

```text
Claude thinks fully.
The system compresses visible state.
If a boundary is hit, continue from the compressed checkpoint instead of bypassing Claude.
```
