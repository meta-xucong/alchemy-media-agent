# Photography Module Foundation Rules

## 1. Classification

All work governed by this document is specialized Photography Template work.

```text
Foundation makes photographic truth reusable.
Photography decides the professional shoot and deliverable set.
General remains simple and scenario-neutral.
E-Commerce retains listing and marketplace deliverable ownership.
```

Photography may configure and activate foundation capabilities. It must not
copy, fork, bypass, or privately replace them.

## 1.1 LLM-First Creative Direction Rule

Photography uses the central remote LLM as the creative decision-maker and
GPT Image 2 as the sole final-pixel renderer. Structured module data is a
constraint and validation layer; it is never a substitute creative director.

The required production chain is:

```text
explicit user controls + pinned profile + reference truth
  -> Central LLM creates the photographic interpretation and one natural-language direction per output role
  -> Photography validates only role coverage, immutable truth, profile rights, reference channels and safety boundaries
  -> frozen shared constraint ledger
  -> shared GPT Image 2 generation
  -> shared real-pixel review / bounded retry / best eligible final delivery
```

Hard rules:

1. Do not use keyword tables, scene defaults, fixed camera sentences, prompt
   recipes, or deterministic role prose as the production source of creative
   direction, scene interpretation, commission intent, composition, lighting,
   lens effect, retouch, or subject behavior.
2. Such structures may exist only as explicit-control validation, capability
   activation evidence, backward-compatible UI defaults, or post-LLM output
   validation. They must not overwrite, pad, replace, or silently narrow the
   LLM's current-prompt interpretation.
3. A Photography production job requires a successful remote Central LLM
   result with exactly one complete natural-language direction per frozen
   deliverable role. Missing, malformed, cardinality-mismatched, or unavailable
   remote creative output blocks the job; it must not fall back to a local
   keyword planner or generic single-image direction.
4. Photography keeps only non-creative hard facts frozen before the LLM:
   user-selected delivery mode and role count, explicit scene control when
   supplied, pinned profile identity/version/checksum, reference-channel
   ownership, preservation locks, safety, and provider capability requirements.
5. A professional-set role taxonomy may require `session_hero`,
   `environmental_context`, and `detail_or_moment`, but the LLM decides each
   role's actual visible photographic solution. The template validates that
   the three solutions are meaningfully distinct; it does not inject stock
   `cover hero`, lens, lighting, pose, or crop prose.
6. A retry receives the same frozen creative record and may add only shared,
   review-supported corrective guidance. It may not re-run deterministic
   scene classification, switch profile, replace the LLM direction, or import
   a General/E-Commerce role recipe.
7. `metadata_only` review is non-certifying. It may record development history
   but cannot pass a Photography P10 quality gate or enable the production
   deployment gate. Certified Photography work requires the shared
   `vision_model` or `hybrid` real-pixel path.

Short form:

```text
LLM creates the photograph.
Photography protects the contract.
GPT Image 2 renders the pixels.
Shared review chooses the final result.
```

## 2. Named Photographer Manual Selection Rule

This is the highest-priority Photography product rule.

1. A named photographer profile may activate only from an explicit frontend
   control selected or confirmed by the user.
2. Runtime activation requires a trusted structured field such as
   `photographer_profile_id` plus `selection_source=user_explicit_ui`.
3. The LLM must never infer, choose, rank, recommend-and-apply, replace, or
   silently mix a named photographer profile.
4. If the user does not select a named profile, the system must use the
   non-named `general_photography` profile.
5. A photographer name appearing only in free text is not activation authority.
   The UI may ask the user to confirm a catalog selection, but generation must
   remain on the General Photography Profile until confirmation is recorded.
6. If an explicitly selected profile is unavailable, disabled, expired,
   region-restricted, or invalid, the job must stop with a clear product-level
   status. It must not silently use General Photography or another photographer.
7. The selected profile ID, version, catalog snapshot, availability decision,
   and selection source must be pinned before generation and retained in audit
   metadata.
8. A retry or continuation uses the same pinned named profile unless the user
   explicitly changes the frontend selection for a new generation action.
9. The LLM may adapt the selected profile's authorized technique package to the
   requested scene, but it may not change the profile identity.
10. Exactly zero or one named photographer profile is supported in the first
    production release. Multi-photographer style blending is forbidden.

Short form:

```text
The user chooses the photographer.
The LLM applies the choice.
No choice means General Photography.
No silent replacement is allowed.
```

## 3. Style Does Not Own Reference Truth

A selected photographer profile owns only explicitly declared photographic
style channels, such as composition tendency, light design, camera relation,
color response, texture, moment treatment, and retouch finish.

It must not override:

```text
portrait identity geometry
animal or non-human subject identity
product structure and markings
required landmark or scene geometry
explicit wardrobe, hair, prop or copy requirements
user-prohibited content or style
```

Doc93 reference-channel ownership remains authoritative. A named profile may
change prompt-owned styling channels, but it receives no additional inheritance
rights over an uploaded reference.

## 4. Named Profile Rights And Availability Rule

Every named profile must be catalog-backed and contain reviewed metadata. At a
minimum:

```text
profile_id
profile_version
public_display_name
profile_kind
rights_status
availability_status
allowed_regions
effective_from
effective_until
source_provenance
review_owner
reviewed_at
technique_package_version
```

The catalog may expose only profiles whose current availability decision permits
use. LLM output, prompt text, uploaded filenames, or historical job metadata
must never create a new catalog entry at runtime.

The system must not present a legal conclusion it has not been given. Rights
metadata is an operator-reviewed product control, not an LLM legal judgment.

## 5. General Photography Default Rule

`general_photography` is a non-named default profile. It must:

```text
use scene-appropriate professional photography grammar
avoid any named photographer identity claim
avoid covertly reconstructing one named profile
allow scene, commission and reference evidence to choose technical modules
remain stable when the LLM is unavailable
```

The Brain may choose scene, commission, lens-effect, lighting, composition,
subject-direction, color, retouch and review modules under the frozen capability
plan. It may not choose a named photographer profile.

## 6. Foundation Versus Photography Ownership

Foundation owns reusable quality capabilities:

```text
universal visual quality
photographic capture realism
human realism
portrait identity
product identity
non-human subject identity
scene continuity
reference channel policy
real-output review infrastructure
bounded rerender and best-result selection
```

Photography owns professional photographic decisions:

```text
commission interpretation
scene-specific shot direction
shot-list and set composition
camera and optical-effect direction
lighting design
subject direction
photographic color and finish direction
photography-specific acceptance profiles
photographic deliverable packaging
```

Reusable photographic primitives may register as evidence-gated shared
capabilities, but professional Photography deliverable maps remain in the
Photography Scenario Pack.

## 7. General, E-Commerce And Other Template Isolation

1. General must not receive Photography shot lists, session roles, named
   profiles, photography-specific UI fields, or professional-set defaults.
2. E-Commerce continues to own listing, white-background, selling-point, A+,
   marketplace and export roles.
3. E-Commerce may later activate reusable camera, lighting or photographic
   realism plugins, but it must not import the Photography Scenario Pack.
4. Brand and New Media may borrow reusable photographic capabilities while
   retaining their own campaign, layout and channel deliverables.
5. Removing or disabling Photography must not break another template or
   historical non-Photography jobs.

## 8. Framework And Renderer Rule

Photography is additive and hot-pluggable. It must use:

```text
ScenarioPackManifest
TemplateCapabilityPolicy
VisualCapabilityManifest
CapabilityActivationPlan
CapabilityContribution
existing Central Brain checkpoints
existing provider and review paths
```

It must not create:

```text
a second Central Brain
a Photography-only generation pipeline
direct provider calls from scene or profile modules
raw prompt-patch plugins
an unbounded retry loop
another final-pixel renderer
```

Doc100 remains authoritative: GPT Image 2 is the sole production final-pixel
renderer. Local analysis may produce metadata but may not alter delivered pixels.

## 9. Structured Contribution Rule

Every hot-pluggable Photography capability must declare:

```text
capability ID and version
activation evidence
dependencies and conflicts
compatible templates
supported profiles
contribution stages
cost and fallback behavior
review issue ownership
retry contribution ownership
```

Modules contribute typed facts, prompt additions, provider input requirements,
review contracts and retry contracts. They must not concatenate uncontrolled
prompt fragments or delete the user's full request.

## 10. Reference-Conditioned Reshoot Rule

An uploaded ordinary photograph must first receive a preservation contract.
The system distinguishes:

```text
faithful enhancement
professional reshoot
creative reinterpretation
```

No mode may guess that every visible source channel should be preserved.
Identity, subject, product, scene, composition, outfit, hair, weather, lighting,
color and whole-image style remain separately owned.

The product should describe GPT Image 2 output as a professional AI reshoot or
recreation when whole-image rerendering is used. It must not imply that the
original pixels received a lossless Lightroom-style edit.

## 11. Review And Retry Rule

Photography review must use:

```text
universal issue codes
+ active foundation capability issue codes
+ active Photography scene/profile issue codes
```

An inactive scene or named profile contributes no prompt, review, retry or score
requirements. Every retry uses the same frozen plan and pinned profile. The
newest result is not automatically the best result.

## 12. Mainline Coordination Rule

The Photography branch must not independently change a shared public contract,
Central Brain contract, provider request, global persistence schema, shared
dependency, lock file, or cross-template interface merely to unblock itself.

When such a need appears:

1. Write a mainline integration request using the format in P04.
2. State the exact blocking implementation point.
3. Stop dependent Photography work without inventing a compatibility hack.
4. Send the request to the user for mainline implementation.
5. After the mainline change is merged, fetch and rebase the Photography branch
   onto the latest `origin/main`.
6. Re-run focused, cross-template and full regression tests.

Registration-only module files may be developed in this branch. A missing
extension hook is a mainline request, not permission to fork the framework.

## 13. Worktree And Git Rule

Photography development uses only:

```text
branch: codex/photography-module
dedicated Photography worktree
base: latest origin/main at each milestone
```

Do not modify another active worktree or its branch. Before each milestone and
before integration, fetch and rebase safely. At every independently verifiable
milestone, test, inspect the diff, commit and push the Photography branch.

## 14. Non-Negotiable Test Rules

Tests must prove:

1. No named profile activates without `user_explicit_ui` selection.
2. Free-text photographer names do not activate profiles.
3. Null selection produces General Photography.
4. Invalid explicit selection blocks instead of silently falling back.
5. LLM output cannot change a pinned profile ID.
6. Selected style does not overwrite identity or other reference truth.
7. Inactive modules contribute zero runtime behavior.
8. General and E-Commerce remain unchanged.
9. Removing Photography leaves the platform runnable.
10. Real-output review compares all attempts and returns the best eligible image.
