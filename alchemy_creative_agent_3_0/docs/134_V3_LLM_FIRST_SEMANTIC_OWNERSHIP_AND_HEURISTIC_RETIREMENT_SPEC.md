# Doc134 V3 LLM-First Semantic Ownership and Heuristic Retirement

Status: forward shared-foundation authority.  This document extends Docs120
and 128 after a controlled real-image audit found that a local keyword check
could overrule an already-frozen Human Realism decision.  It applies to every
template.  It creates no children, apparel, commerce, General, or Photography
creative recipe.

## 1. The defect this closes

The controlled request asked for a real photograph of a person wearing a
reference-bound garment whose surface included a cartoon graphic.  The remote
Brain was used and the enforced plan activated Human Realism.  A later local
string scan nevertheless read `cartoon` as the rendering medium of the entire
image and disabled Human Realism.

That is an ownership violation.  A word describing an object surface cannot
silently become a decision about the output medium, and an executor cannot
veto a frozen active capability by reclassifying intent from prompt text.

## 2. Forward ownership rule

For a real-image task the forward path is:

```text
protected user intent + permitted reference truth
-> remote Central Brain semantic decision + creative direction
-> frozen task profile / activation plan / constraint ledger / envelope
-> shared capability execution
-> remote Central Brain canonical Provider-prompt sign-off
-> GPT Image 2 materialization of that exact prompt
-> shared real-pixel review, bounded retry, final delivery
```

The remote Brain owns creative and semantic interpretation.  It must return a
small `rendering_intent` decision:

| Field | Values | Purpose |
| --- | --- | --- |
| `rendering_mode` | `photoreal`, `stylized`, `mixed`, `unknown` | The medium of the requested complete output. |
| `stylization_scope` | `whole_image`, `object_surface`, `none`, `ambiguous` | Whether a stylized term describes the frame or a factual object detail. |

This is not a prompt vocabulary, visual recipe, demographic classifier, or
free-form casebook.  It is the minimum semantic boundary needed to keep a
cartoon print, anime label, illustrated book cover, or similar object truth
from being mistaken for a request to stylize the full image.

### Canonical Provider-prompt invariant

The final text submitted to an image Provider is a Brain-issued canonical
prompt, not a local string assembly.  Before it signs that prompt, the Brain
receives only the frozen protected user intent, permitted reference facts, its
own frozen draft direction, TemplateDeliverablePlan,
CapabilityExecutionEnvelope, and ResolvedConstraintLedger.  It returns:

- exactly one complete natural-language `canonical_provider_prompts[]` item
  per materialization operation; and
- `review_status=approved` for each item, which is the Brain's concise
  sign-off that it reconciled frozen facts, user constraints, rendering
  semantics, and active shared-quality obligations.

The runtime attaches the deterministic binding to the frozen Brain plan,
envelope, ledger, deliverable ordinal, reference binding and prompt hash. It
does not generate, edit, compact, or supplement the Brain's natural language.

The Provider materializer may validate that binding, select the declared image
operation and input files, and pass technical API parameters.  It must not
append creative, Human Realism, scene, camera, style, review, retry, role, or
keyword-derived prompt fragments.  If the canonical prompt is absent, stale,
or mismatched, the operation blocks before the Provider.

Real-pixel review remains independent: it evaluates a rendered image, not the
prompt.  If a shared bounded retry is authorized, the semantic review result
is first resolved into the frozen retry ledger and sent back to the Brain.  The
Brain produces a new complete canonical prompt for that retry; local code may
not concatenate a retry patch onto the prior prompt.

For an LLM-first real-image request with visible-person evidence, a missing or
invalid remote `rendering_intent` is a fail-closed remote semantic-contract
failure.  A deterministic fallback may retain only a conservative,
auditable interpretation for non-LLM legacy/draft paths: it may recognise an
explicit whole-image stylization command or explicit technical exclusion, but
must never turn an incidental art word into a creative decision.

## 3. Execution invariant

1. The activation planner reads the frozen rendering intent.  A visible
   person activates Human Realism unless the frozen intent explicitly says the
   *whole image* is stylized.
2. An enforced active Human Realism capability must execute.  Its local layer
   may not independently disable itself from a raw keyword scan.
3. If a reused frozen plan says Human Realism is active while the frozen
   rendering intent says the whole output is stylized, V3 blocks with a
   structured execution mismatch.  It must not silently choose either side.
4. Object-surface artwork remains product/reference truth.  It does not add a
   style lock or change the remote Brain's scene, composition, wardrobe, or
   mood ownership.
5. The Provider receives only the concise, resolved Human Realism contract.
   It reaches the Provider only after the Brain has incorporated it into the
   canonical prompt.  The Provider never receives a casebook, a keyword
   trail, raw reviewer codes, or a long list of facial micro-instructions.

The existing Doc124 safety-sensitive-person boundary remains unchanged.  It
only limits framework-owned wording.  It must still leave one concise,
ordinary real-camera-naturalness contribution when shared Human Realism is
active; it does not create a child route or a child prompt recipe.

## 4. Audit classification for local logic

Local code is allowed only in the following categories:

| Class | Permitted examples | Not permitted |
| --- | --- | --- |
| Technical admission | MIME/decode/size checks, hashes, reference availability, exact count/size contracts, provider error classification | Choosing an artistic style or scene from words. |
| Explicit safety/contract guard | User's direct no-person/no-text instruction, frozen-envelope consistency, policy result handling | Guessing creative meaning or rewriting a user subject. |
| Read-only compatibility | Displaying historical mode/recipe/keyword metadata | Re-emitting it into a new Brain request, Provider prompt, review, retry, or delivery. |

The following categories are LLM-owned on a new LLM-first task and must be
retired from forward local execution: rendering medium, subject/scene genre,
creative mood, artistic composition, platform visual strategy, photography
scene direction, and any decision inferred from a word-list or regex beyond a
direct technical/safety assertion.

## 5. Audited residuals and migration rule

The audit found historical keyword and recipe code in the general creative
rules, activation fallback, Human Realism, reference-channel interpretation,
old suite/mode directors, Photography scene classification, and optional
condition sidecars.

- The Human Realism and activation-fallback paths are forward-critical and
  are corrected by this document.
- General, E-Commerce, and Photography remote-native Provider paths must be
  regression-guarded so local role/recipe/mode text cannot enter their new
  Provider prompts.
- Reference ownership may use declared asset roles and explicit user controls
  as evidence, but ambiguous channel intent belongs to the remote Brain and
  frozen ledger rather than proximity regexes.
- Optional/no-op condition sidecars and old mode/role recipe structures may
  remain readable for old records only.  They must not select reference truth,
  create creative direction, or reach a new GPT Image 2 request.

No migration may solve this by expanding keyword lists, adding demographic
branches, adding prompt atoms, or restoring static scene/camera/marketing
recipes.  Each retirement must prove General, E-Commerce, and Photography
isolation.

### 5.1 Forward-path reachability audit

The following audit classification is binding for the current implementation.
It separates legitimate deterministic work from retired creative ownership;
it does not treat all parsing as an error.

| Surface | Forward LLM-first status | Permitted remaining role |
| --- | --- | --- |
| `ScenarioRuntime -> provider_prompt_finalize` | Active | Sends only frozen facts, semantic decision, reference bindings, normalized review evidence and opaque integrity bindings to the remote Brain. |
| `ProductionImageGenerationProvider._generation_prompt` | Active guard | Returns the approved Brain text verbatim. A real-image marker with no signed prompt blocks instead of entering the legacy assembler. |
| Product API visual retry patch builder | Retired from forward path | Brain-signed jobs retain only normalized issue codes and retry provenance. They do not create a local patch, face-mask repair instruction, negative list, or retry prompt. The Brain signs the replacement whole prompt. |
| Human Realism and activation fallback string checks | Compatibility/fallback only | May make a conservative auditable decision only where no LLM-first remote semantic contract exists. A frozen remote decision overrides them. |
| Central Brain prompt compiler, suite/mode directors, legacy role recipes | Compatibility/read-only on LLM-first materialization | They may preserve legacy planning/history records and structural lineage. Their text is not read by the canonical Provider materializer. Raw human/cartoon keyword matching no longer starts or suppresses an automatic identity chain; new jobs require frozen Brain subject evidence. |
| Condition-engine keyword selectors | No-op sidecar/history only | May report a legacy condition record; they cannot select a V3 Provider input, produce a renderer prompt, or override frozen reference bindings. |
| Photography brief/scene directors | Structural contract only | Role count, immutable profile binding and declared reference channel are whitelisted to the remote Brain. Local scene, camera, lighting, pose and shot wording is not. |

The word `cartoon`, `anime`, a seller label, a filename, a scenario preset, or
an old review issue may therefore never become a new Provider instruction by
itself.  It can be a fact/evidence item for the remote Brain, which is the
only component permitted to decide whether it matters to the complete image.

## 6. Required regression matrix

1. Remote Brain identifies a real photograph with a cartoon/anime/manga/
   illustrated object surface as `object_surface`; Human Realism remains
   active and reaches the resolved Provider contract.
2. An explicit whole-image cartoon/anime/illustration request is classified
   as `whole_image`; Human Realism is not activated.
3. A missing remote semantic decision for an LLM-first real visible-person
   task blocks before capability execution or Provider materialization.
4. An enforced active Human Realism plan cannot be locally disabled by raw
   prompt text; a genuine frozen-plan contradiction blocks explicitly.
5. Adult portrait, safety-sensitive young person, product-on-person,
   non-person product, and a true stylized illustration prove shared behavior
   without cross-template or demographic leakage.
6. New remote-native General, E-Commerce, and Photography prompts contain no
   old static recipe/mode/keyword-derived creative content.
7. A Provider request carries a canonical-prompt hash that matches the frozen
   Brain sign-off exactly. Missing/mismatched bindings block before any
   Provider request; a shared retry receives a separately signed complete
   prompt rather than a local text append.
8. A retry for a Brain-signed job persists normalized issue codes and
   provenance only.  It must neither create a local `retry_patch` nor run the
   optional face-local repair route; the retry sign-off call is the sole
   renderer-language author.

## 7. Implementation status

Phase A is implemented by the shared runtime: LLM-first jobs require a remote
rendering-semantics decision, freeze the active capability/ledger/envelope,
then invoke `provider_prompt_finalize`. The Provider reads that sign-off
verbatim. Existing frozen non-retry jobs reuse their signed prompt; a bounded
retry invokes the sign-off stage again with resolved review evidence, never a
local retry string. Historical/draft compatibility paths remain readable but
cannot certify an LLM-first real-image delivery.

## 8. Historical interpretation

Docs68-72 casebook mechanisms, old deterministic industry/scenario/tone
classification, and legacy mode/role recipes remain historical compatibility
evidence only.  They must not be cited as authority for a newly created
LLM-first V3 job.  Doc120's earlier illustration-only correction is subsumed
by this broader semantic-ownership rule.
