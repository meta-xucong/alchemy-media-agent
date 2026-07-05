# 68C V3 Doc68 Validation And Acceptance Matrix

Status: auxiliary validation matrix for Doc68.

## 1. Focused Test Matrix

```text
test_doc68_casebook_helper_is_v3_owned
  verifies no V1/V2 runtime imports and helper lives under visual_cluster

test_doc68_human_photorealism_consumes_casebook_recipe
  verifies skin, expression, camera, anti-AI-face, and reference cleanup rules

test_doc68_four_modes_receive_distinct_casebook_overlays
  verifies selection/delivery/exploration/layout modes differ by prompt pressure

test_doc68_product_lifestyle_recipe_is_stronger_than_safe_studio_only
  verifies context/lifestyle role includes lived-in scene guidance

test_doc68_ecommerce_vertical_pack_reuses_casebook_without_losing_pack_ownership
  verifies ecommerce pack keeps owner metadata while reusing Doc68 product overlay

test_doc68_provider_consumes_casebook_metadata_without_owning_strategy
  verifies provider prompt includes casebook lines from metadata only

test_doc68_general_prompt_stays_deproductized
  verifies pure General Template does not receive ecommerce/product claims
```

## 2. Regression Matrix

Run after code changes:

```text
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc68_casebook_guided_quality.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_doc67_boundary_quality.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_human_photorealism_layer.py alchemy_creative_agent_3_0/tests/test_v3_mode_aware_role_director.py -q --tb=short
python -m pytest alchemy_creative_agent_3_0/tests/test_v3_provider_output_production.py alchemy_creative_agent_3_0/tests/test_v3_general_prompt_deproductization.py -q --tb=short
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests src_skeleton/app .codex-longrun
git diff --check -- alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/docs alchemy_creative_agent_3_0/tests .codex-longrun
```

## 3. Real Portrait Validation Prompt

Use the stable Doc61/Doc67 portrait prompt so results can be compared:

```text
Create a summer cool East Asian beauty portrait set for a social cover campaign.
The same young woman has subtle green-highlighted dark hair, clean white summer
styling, fresh seaside light, bright blue-green color mood, refined commercial
photography finish, no visible text, no product, no packaging.
```

Continuation check:

```text
same person direction
same broad face/body/hair/wardrobe direction
more natural skin and expression than earlier runs
different expression, gaze, head angle, pose, crop, and camera distance
no cloned stills
no watermark, AI badge, random text, or unrelated product
```

## 4. Real Product Validation Prompt

Use a product/lifestyle prompt:

```text
Create a commercial image set for a chilled summer citrus drink can with a
fresh blue-green color mood. The set should include a clear product hero,
a lived-in summer cafe or outdoor lifestyle context, a close material/detail
frame, and a layout-safe cover image. Preserve product identity and avoid
random text, fake badges, watermark, or unrelated extra products.
```

Product checks:

```text
product identity remains clear
label/logo remains readable if supplied as reference
at least one image feels genuinely lived-in or contextual
roles are visibly different
no fake feature badges or AI generated marks
no random text or watermark
```

## 5. Manual Lovart Comparison Rubric

Rate with plain bands:

```text
commercial finish:
  weak / usable / strong / excellent

identity or product consistency:
  drift / directional / strong / very strong

role separation:
  collapsed / partial / clear / directed

realism:
  AI-feeling / acceptable / natural / high-trust photographic

project continuity:
  weak / useful / strong / Lovart-like
```

Doc68 is successful if the outputs improve in realism and role direction without
breaking V3 modular boundaries. It does not have to eliminate every provider
artifact from a single unstable upstream run.
