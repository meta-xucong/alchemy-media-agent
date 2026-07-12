# E08 Test and Acceptance Matrix

## Contract tests

- platform profile has version, status, market, and source metadata;
- stale/unknown profiles degrade safely;
- category pack has required evidence and review checks;
- recipe has one slot goal and product-truth constraints;
- localized copy preserves protected facts;
- export manifest records profile and category versions;
- public requests reject provider-level controls.

## Planner tests

- platform changes slot priority without changing Central Brain;
- category changes evidence roles without changing platform policy;
- requested image count is respected exactly;
- missing facts produce warnings instead of invented values;
- duplicate roles are removed or explained;
- suite roles remain differentiated;
- selected explicit slots are not silently expanded;
- product visual positioning reaches every selected recipe without creating a
  price, discount, award, certification, or provenance claim;
- Amazon main-image recipes apply the verified primary-image baseline, while
  secondary recipes retain evidence roles without an invented policy override;
- Ozon and other profiles do not gain a scene-led or fixed-ratio rule by
  default; an optional seller-selected strategy applies only to compatible
  roles and remains separately auditable;
- historical `platform_visual_intent_id` jobs remain readable while new jobs
  use evidence/compliance/strategy metadata.
- fact-ledger source, verification, channel, and allowed-slot bindings remain
  auditable; blocked facts cannot reach a recipe, copy plan, or export binding,
  while confirmation facts create a publish-check warning.
- the Amazon apparel benchmark plans a distinct primary, worn-front,
  back-or-side, detail, lifestyle, fit/size, and styling-versatility role;
  a supplier-provided visual fact that is absent from the reference remains an
  explicit export publish-check attention, not silent product truth. D4 adds
  persisted owner confirmation before final delivery.
- General Template does not receive commerce suite metadata.

## Isolation tests

- no V1/V2/Lab import or storage access;
- no provider call from E-Commerce planner/category code;
- no marketplace fields in General Template UI or prompt defaults;
- shared Human Realism/Product Identity behavior remains in the shared cluster;
- inactive capability contributions are empty;
- locked/disabled templates cannot create jobs;
- historical jobs remain readable.

## Review and retry tests

- product drift is caught for product jobs;
- fake claims, fake certificates, and invented specs are warnings/failures;
- conservative main-image text default is enforced, and any verified platform
  restriction is recorded separately from that default;
- approved literal copy is carried only in provider-native complete-image
  requests; no local OCR, composition, safe-area, or private text retry path
  is introduced;
- historical local-text inputs return `provider_native_required`, and no
  production text-suite claim is allowed before Doc111 Provider Gate C/D;
- retry-superseded outputs stay folded from delivery;
- best-reviewed candidate wins over newest candidate;
- out-of-scope review issues do not trigger commerce retries.

## UI tests

- beginner can upload product, select platform/category, and generate;
- advanced fields are hidden initially;
- suite cards show image, slot label, purpose, and action;
- planned suite rows expose separate plain-language evidence, strategy, and
  verified-platform-restriction labels where applicable;
- user-directed single-slot redo remains unavailable until the Doc105 shared
  continuation route, lifecycle, resolver, and browser coverage are accepted;
- selected references persist after refresh;
- rejected direction is carried forward;
- export summary is plain language;
- mobile output board remains image-first.

## Real-output fixture matrix

Run at least one real product fixture for each first-release category across:

```text
Amazon/en-US
Ozon/ru-RU
Taobao or Tmall/zh-CN
TikTok Shop/en-US or market equivalent
```

Each run must inspect:

- product shape, color, material, logo, packaging, and quantity;
- text accuracy and language;
- human hands/models when present;
- scene realism;
- slot differentiation;
- verified primary-image restrictions, conservative text default, and the
  source/evidence tier of each placement constraint;
- final file resolution and export names;
- retry history and delivery count.

### External Amazon apparel benchmark

`E10_EXTERNAL_AMAZON_APPAREL_BENCHMARK.md` defines the first retained visual
benchmark card. Its screenshots are not repository assets and must not be used
as pixel-match test data. The automated E24 fixture tests the role map and
unverified-fact contract; a real-provider run must score product fidelity,
slot differentiation, Amazon main-image compliance, human realism, and
provider-native literal-copy/claim acceptance before it can become an accepted
regression fixture.

## Activation gate

E-Commerce may be marked active only when:

1. E00-E11 are accepted.
2. All contract, planner, isolation, review, retry, and UI tests pass.
3. Real-output fixtures pass manual visual review.
4. Product references and project_id are enforced.
5. Profile versions are frozen per job.
6. General Template remains unaffected.
7. Export manifest and publish-check warnings are visible.
8. No unsupported platform-compliance promise is made.

## Required verification commands

```powershell
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_ecommerce_doc26_scenario_pack.py -q
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests
node --check src_skeleton/app/static/app.js
git diff --check
```
