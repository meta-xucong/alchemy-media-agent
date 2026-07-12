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
- main-image text policy is enforced per profile;
- final-pixel OCR/vision issues trigger only bounded provider-native revisions;
- retry-superseded outputs stay folded from delivery;
- best-reviewed candidate wins over newest candidate;
- out-of-scope review issues do not trigger commerce retries.

## UI tests

- beginner can upload product, select platform/category, and generate;
- advanced fields are hidden initially;
- suite cards show image, slot label, purpose, and action;
- one slot can be regenerated;
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
- platform-specific main-image and text policy;
- final file resolution and export names;
- retry history and delivery count.

## Activation gate

E-Commerce may be marked active only when:

1. E00-E08 are accepted.
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
