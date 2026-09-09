# V3 Human-Led Suite and Canonical Source Closure

Status: implementation candidate; acceptance requires focused regression tests,
independent audit, local real-image validation, GitHub push, and governed VPS
release verification.

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
