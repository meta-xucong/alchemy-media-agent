# V3 Human-Led Suite and Canonical Source Closure

Status: implementation accepted in local validation; GitHub push and governed
VPS release verification are recorded below.

## 1. Scope and evidence

This is V3 foundation work. It repairs the shared Brain source projection,
provider audit projection, and neutral General visual capability routing. It is
not a new vertical template and it does not add an e-commerce deliverable map
to General Template.

The triggering run was the adult-woman supermarket/beverage-aisle project:

- project: `project_200ef57976`
- observed job: `job_eef1766a33`
- observed release: `62422dad6a36a05bb24f502afc9f94ae65a02c90`
- current mainline baseline before this repair: `59c7b76c91b251af351001114148b99fd615cd4b`

The observed release produced two nearly duplicate images, classified the
human-led scene as `subject_type=product`, emitted `hero_object` and
`context_scene` roles, and recorded provider prompts around 660 Unicode
characters. Its metadata also showed `user_direction_lossless=false` even
though the canonical records claimed a preserved user-direction receipt.

The release is an independently managed detached worktree on the VPS. The
current mainline already contains the Doc293 unified prompt policy and Doc294
complete Brain source projection, but that code was not present in the observed
release. Therefore a real acceptance run must use the exact pushed mainline
commit, not the historical release worktree.

## 2. Theory-first correction model

### Intended behavior

For a fresh enforced V3 real-image request:

1. The complete user direction, Brain planning result, active capability
   guidance, protected constraints, and variation contract reach the Brain
   finalizer through one source projection.
2. The Brain is the only semantic author of the final renderer prompt. The
   provider forwards that exact signed prompt without a local compactor or
   creative suffix.
3. In General Template, a scene containing a visible person and a visible
   product keeps product truth active, but the visible person remains the
   primary subject. The suite therefore uses human roles while the product
   capability remains available for the held object.
4. Multi-output provider audit selects the integrity receipt for the actual
   output index. A valid canonical receipt is not reported as unverified merely
   because the batch has more than one output.

### Observed mismatch and owning layer

| Mismatch | Owner | Cause |
| --- | --- | --- |
| VPS final prompt remained thin | release/deployment plus Brain source contract | VPS ran a pre-Doc293/294 release; the old route had no complete source projection |
| Canonical multi-output audit reported lossless=false | Provider audit projection | `_brain_user_direction_integrity` returned empty unless the batch had exactly one record |
| Person holding a bottle became product suite | ScenarioRuntime plus shared visual capability cluster | General's compatibility `product_profile` is non-empty; `bool(request.product_profile)` froze a false product binding, then `allow_product_language` also won before visible-person evidence |
| Two images were nearly the same | downstream effect of wrong role family, not a retry threshold problem | `hero_object`/`context_scene` were selected for a human-led General scene |
| Review rejected metadata-only outputs | review/evidence gate | review evidence was incomplete; thresholds must not be lowered to hide the source/role defect |

### Authority decisions

- Brain semantic completeness remains authoritative. Local code may validate
  typed receipts and source digests, but must not invent keyword checks,
  minimum-length heuristics, or a second prompt author.
- Doc293/294 source projection and exact canonical prompt forwarding remain the
  single prompt path for enforced real images.
- Product language permission is an orthogonal capability flag. It does not
  decide the primary subject or replace visible-person evidence.
- For non-e-commerce General requests, a Brain-typed visible person takes
  precedence over a co-visible product for primary subject/role selection.
  E-Commerce keeps its product-truth authority and remains isolated.
- Review and retry gates stay unchanged until a correctly sourced and correctly
  typed real output is available for evaluation.

## 3. Minimal complete repair

1. Make the provider use one shared selector for the approved canonical record
   and resolve `user_direction_integrity` by the request's output index,
   preserving exact canonical prompt text and the Brain semantic receipt.
2. In ScenarioRuntime, use typed product facts—not a non-empty compatibility
   envelope—to create a pre-Brain General product binding.
3. In the shared visual cluster, separate “product wording is allowed” from
   “product is the primary subject.” Make visible-person precedence explicit in
   General, then carry that primary subject through identity locks, references,
   mode quality, and suite role planning. Explicit product references remain
   product truth bindings even inside a human-led frame.
4. Add regression coverage for:
   - a two-output canonical audit;
   - an enforced General mixed person/product profile;
   - E-Commerce isolation;
   - source projection and canonical prompt forwarding already covered by
     Doc293/294.
5. Freeze and independently audit the candidate commit before any external
   mutation. Run local real generation with the same original test direction,
   inspect final prompt/source receipts and pixels, push the verified commit,
   then deploy that exact SHA through the governed release migration script.

## 4. Non-goals and safety boundaries

- no prompt-length threshold relaxation;
- no local semantic keyword or substring acceptance test;
- no review threshold reduction and no suppression of face/aesthetic warnings;
- no provider/model replacement;
- no General Template e-commerce suite or platform-specific deliverable map;
- no V1/V2 storage or API bridge;
- no deletion or cleanup of pre-existing validation evidence;
- no deployment from the stale `62422dad` release.

## 5. Acceptance evidence

The final completion record must include the fixed scope, focused and broader
tests with results, independent audit result, local real-image job/output
identifiers and visual assessment, commit SHA, GitHub push verification, VPS
release path/health verification, and any remaining external dependency.

Task routing uses `multi-agent-dev` contract `v1.3.1-route-guard`, complexity
gate `ESCALATE_REQUIRED`, one mainline writer, and an independent read-only
audit after the candidate version is frozen.

## 6. Implementation and acceptance record

### Implemented correction

The repair was delivered on the mainline in three bounded commits:

- `8d6cf558` — correct General human-led suite precedence and replace the
  multi-output integrity singleton assumption with output-aware selection.
- `070fd871` — close the Brain canonical-record contract: strict output-index
  binding, valid same-record user-direction integrity, General aliases for
  `person`/`human`/`character`, runtime-binding reconciliation, and one shared
  typed product-fact authority.
- `28b4d332` — fail closed for malformed canonical prompt types and loose
  string-valued Character Card slot-delta flags; add regression coverage.

No prompt threshold was relaxed, no local prompt author was added, and no
review threshold or General vertical deliverable map was changed.

### Audit and regression evidence

The independent audit rounds were run as read-only work. The first frozen
candidate was intentionally rejected by the auditors for three defects:
provider receipt closure, inconsistent human vocabulary, and duplicated
product-fact authority; a second audit also found the pre-Brain product role
binding could override a Brain-typed visible person. Those findings were
closed before the final commit. The final fixed diff was then checked against
the same call path and exercised by these offline regression groups (external
Brain and Vision disabled):

| Scope | Result |
| --- | --- |
| Doc293 + Doc294 + Doc295 + Provider output | `110 passed` |
| Project Mode | `78 passed` |
| General role director + de-productization + prompt/replay | `36 passed` |
| Foundation visual/reference/LLM ownership | `25 passed` |
| Frontend generation-mode repair + desktop/mobile contract | `23 passed` |
| Python compileall, Node desktop/mobile syntax, `git diff --check` | passed |

The Doc290 lean-request suite could not be collected in the local V3 virtual
environment because its transitive legacy fixture imports `playwright`, which
is not installed there. This is an environment dependency, not a failure from
the changed files; the focused Brain/Provider suites above passed.

### Local real-image acceptance

The exact original user direction was read from
`.media_storage/v3_projects/project_f49cb9b5da/project.json`, not retyped:

- prompt length: `2196` characters;
- SHA-256: `f37928b680e56b7258583f0ab27b4232ea5bafe68703d3fb8628bde3b6a5d2d7`;
- valid-path real generation ran on `070fd871`; `28b4d332` only adds
  fail-closed handling for malformed receipts and leaves valid receipt
  forwarding unchanged;
- replay: `general_template`, `campaign_poster`, `delivery_suite`, two outputs;
- project/job: `project_df88c957e6` / `job_0a78458a76`;
- outputs: `v3_output_61e3bb20eef74ab79954` and
  `v3_output_f935a5b7092f43429275`.

Both Brain canonical records were `approved + complete + preserved`, with
canonical prompt lengths `3093` and `2367`. Both Provider audits reported
`prompt_source=remote_brain_canonical`, `user_direction_lossless=true`, and
`user_direction_semantic_status=preserved`. The active shared capability set
was `visual_grammar`, `universal_visual_quality`, `commercial_quality`,
`human_realism`, and `suite_direction`; no E-Commerce capability was loaded.

The two real outputs were distinct: the first is a full-body environmental
hero frame showing the supermarket aisle, crouched pose, bottle, shelves and
heels; the second is a closer subject/detail frame with the same person,
wardrobe, bottle and aisle context. The hybrid pixel review verified both with
`status=pass`, `verification_state=verified`, no detected issues, and delivered
exactly two outputs. The provider returned its standard vertical `1024x1536`
canvas; the user direction's 3:4 requirement remained present in both Brain
prompts, while the replay did not include an explicit image-size option.

Local evidence files:

- `.controlled-validation/doc295-local-real-20260910-rerun/result.json`
- `.controlled-validation/doc295-local-real-20260910-rerun/output-1-v3_output_61e3bb20eef74ab79954.png`
- `.controlled-validation/doc295-local-real-20260910-rerun/output-2-v3_output_f935a5b7092f43429275.png`

### Release record

- final code audit commit: `28b4d332aa907b0aeb9cb26c2050491ca88ad1aa`;
- GitHub push: pending at document authoring time;
- VPS release/health: pending at document authoring time.
