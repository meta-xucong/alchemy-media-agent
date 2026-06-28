# 26 E-Commerce Scenario Pack And Commerce Capability Spec

This document defines the future E-Commerce Scenario Pack.

It must be implemented and activated only after:

1. `23` V3 foundation gaps are complete.
2. `24` shared capability modules are available.
3. `25` General Creative deltas are integrated without turning General Creative into an e-commerce tool.
4. `27` commercial frontend shell exists with the shared Scenario Hub, General Creative workspace, and locked E-Commerce placeholder.

Backend-only contract exploration may be drafted before the full UI is active,
but user-facing E-Commerce generation must not be enabled until the document
`27` shell can host it as a normal V3 Scenario Pack rather than a separate app.

## Product Goal

The E-Commerce Scenario Pack should let a user provide:

1. product image(s)
2. a simple prompt or product description
3. optional platform/market choice
4. optional product specs
5. optional keyword/competitor/listing references

Then the agent should generate a mature e-commerce image set that can be directly used or lightly edited for listing, advertising, or store assets.

The user should not need to understand prompt engineering, image-control parameters, marketplace image strategy, or visual grammar extraction.

## Relationship To V3 Core

E-Commerce is not a replacement for the central brain.

It is:

1. a Scenario Pack
2. a commerce-specific policy layer
3. a consumer of shared capabilities
4. an owner of commerce-specific planning/evaluation/export logic

It is not:

1. a separate app
2. a fork of V2
3. a pile of prompts inside UI code
4. a direct provider router
5. a direct importer of V1/V2 services

## Required Package

Add:

`app/scenario_packs/ecommerce/`

Suggested files:

| File | Responsibility |
| --- | --- |
| `manifest.py` | Scenario id, modes, required inputs, supported platforms, capability bundle. |
| `pack.py` | E-Commerce Scenario Pack implementation. |
| `contracts.py` | Commerce-specific product-level contracts. |
| `product_truth.py` | Product truth lock and factual preservation. |
| `commerce_brief.py` | Market/user/competitor/keyword/selling-point synthesis. |
| `marketplace_rules.py` | Platform profile and image-position policy. |
| `selling_point_planner.py` | Converts commerce insight into image set recipes. |
| `copy_bridge.py` | Uses listing copy concepts to support image text and visual hierarchy. |
| `commerce_critic.py` | Candidate review for clarity, trust, compliance, and conversion fit. |
| `export_packager.py` | Platform-aware export naming, dimensions, and package summary. |

## E-Commerce Modes

Start with these modes:

| Mode | User Promise | Output |
| --- | --- | --- |
| `one_click_product_set` | Upload product image + short prompt, get a mature image set. | Main image, feature images, scenario image, detail image, optional comparison/trust image. |
| `marketplace_listing_set` | Prepare listing-ready visuals for a selected platform/market. | Platform-aware image sequence and export package. |
| `style_recreation_set` | Upload competitor/style reference and product image, generate a legal reusable style direction. | Similar visual grammar, different content and product truth. |
| `ad_creative_set` | Generate ad covers and campaign images from product facts. | Ad-oriented hero, benefit hook, social cover variants. |
| `listing_visual_copy_pack` | Generate visual text hierarchy alongside images. | Image recipes with suggested overlay text, not just prompts. |

Do not expose all modes at once if UI simplicity suffers. The default should be `one_click_product_set`.

## Commerce Thinking Model

The E-Commerce agent should internalize the seller workflow:

| Seller Thinking | Agent Capability |
| --- | --- |
| What do I have? | ProductTruthLock and product profile extraction. |
| What does the market want? | CommerceIntelligenceBrief and audience/motivation/pain-point inference. |
| What do competitors show? | CaseLibraryRetriever plus optional competitor listing/case analysis. |
| How should I present it? | SellingPointToImagePlanner and MarketplaceRuleEngine. |

This logic should be invisible to the beginner user. The UI should ask for simple inputs, while the LLM-led central planning flow performs the intermediate reasoning.

## Commerce Contracts

### ProductTruthLock

Purpose:

Prevent the agent from generating a beautiful but wrong product.

Fields:

| Field | Meaning |
| --- | --- |
| `product_category` | Normalized category. |
| `visible_attributes` | Shape, material, color, logo, components, texture, package, count. |
| `immutable_attributes` | Facts that must not change. |
| `allowed_scene_changes` | Environment, props, lifestyle context, background changes. |
| `forbidden_transformations` | Shape, logo, material, quantity, certification, size, or function changes that are not allowed. |
| `evidence_sources` | Uploaded image, product specs, user text, listing text, manual correction. |
| `confidence` | Confidence per fact. |
| `review_obligations` | What later review must check. |

### CommerceIntelligenceBrief

Purpose:

Convert product facts, user prompt, market direction, and optional competitor/listing data into conversion-oriented creative strategy.

Fields:

| Field | Meaning |
| --- | --- |
| `target_audience` | Buyer segments and usage scenes. |
| `buying_motivations` | Why buyers choose this product type. |
| `pain_points` | What buyers fear or dislike. |
| `trust_drivers` | Proof points, safety, durability, quality, after-sale confidence. |
| `keyword_intent_map` | Keyword roots and user intent, if provided. |
| `competitor_patterns` | Common competitor strengths, weaknesses, scenes, and visual conventions. |
| `differentiated_selling_points` | Ranked reasons to buy this product. |
| `visual_strategy` | How those reasons become image concepts. |
| `claim_risk_warnings` | Claims that need evidence or softer language. |

### MarketplaceRuleProfile

Purpose:

Keep outputs aligned with platform/market expectations.

Fields:

| Field | Meaning |
| --- | --- |
| `platform` | Amazon, Shopify, TikTok Shop, Taobao, JD, Pinduoduo, generic, etc. |
| `market` | US, EU, JP, CN, etc. |
| `image_slots` | Main image, secondary image, A+ image, ad cover, store banner. |
| `canvas_rules` | Aspect ratio, safe area, text density guidance. |
| `content_rules` | Product visibility, claim limits, prohibited overlays, required clarity. |
| `export_rules` | Naming, size, format, package grouping. |

Important:

Marketplace rules change over time. Do not hard-code unstable platform policy as permanent truth. Store profile version and update date in metadata.

### EcommerceAssetRecipe

Purpose:

Define each output image before generation.

Fields:

| Field | Meaning |
| --- | --- |
| `slot` | Main image, feature image, scenario image, detail image, comparison image, trust image, ad cover. |
| `business_goal` | Click, understand, trust, compare, desire, remember. |
| `selling_point` | One primary point per image. |
| `buyer_intent` | The buyer need this image addresses. |
| `required_product_facts` | Facts that must remain visible/correct. |
| `visual_scene` | Background, props, people, context, lighting, composition. |
| `overlay_text` | Optional short text derived from copy strategy. |
| `reference_bindings` | Product/style/layout/logo references used. |
| `review_checks` | Candidate must pass these checks. |

## Shared Capabilities Used By E-Commerce

E-Commerce should use the modules from `24` as follows:

| Shared Capability | E-Commerce Use |
| --- | --- |
| AssetRoleAnalyzer | Detect product image, logo, style reference, competitor reference, background reference. |
| AssetBindingPlanner | Preserve product truth while allowing scene/style changes. |
| CaseLibraryRetriever | Retrieve category/platform creative patterns and competitor-like visual grammar. |
| VisualGrammarLockModule | Recreate high-value image structure without copying content directly. |
| InformationIntegrityLockModule | Protect product specs, logo, required copy, and claims. |
| PromptConstraintCompiler | Convert commerce recipes into prompt/layout/evaluation constraints. |
| OutputReviewModule | Check product clarity, listing fit, trust, and compliance. |
| HistoryReferenceModule | Keep brand/store style consistent across product sets. |

## Commerce-Specific Capabilities

### ProductTruthLock

Input:

1. uploaded product images
2. product description
3. product specs
4. user corrections

Output:

1. immutable product facts
2. allowed creative freedom
3. unsupported claim warnings
4. review checklist

### CommerceBriefBuilder

Input:

1. product truth
2. user prompt
3. target platform
4. optional keywords
5. optional competitor/listing references

Output:

1. target buyer
2. top motivations
3. pain points
4. proof/trust needs
5. ranked selling points
6. visual strategy

### SellingPointToImagePlanner

Input:

1. commerce brief
2. platform rule profile
3. available assets

Output:

1. image sequence
2. one primary job per image
3. required product facts per image
4. overlay text suggestions
5. reference requirements

### MarketplaceRuleEngine

Input:

1. platform
2. market
3. output slot

Output:

1. rule profile
2. canvas/safe area constraints
3. text density guidance
4. export requirements
5. compliance warnings

### EcommerceCopyBridge

Purpose:

Use Amazon-style copywriting thinking to support visuals, not to turn the image agent into a full listing copywriter by default.

It can extract:

1. core keyword roots
2. buyer intent
3. feature-benefit language
4. short overlay text
5. comparison/trust proof wording

It should not force the long title/bullet workflow on beginner image users.

### CommerceCritic

Review each candidate for:

1. product correctness
2. product visibility
3. key selling point clarity
4. buyer-intent fit
5. platform slot fit
6. trust/claim risk
7. text readability
8. set consistency

## User Interaction Design

The default flow should be simple:

1. Upload product image.
2. Type a short request, such as "make a premium Amazon image set for this desk lamp".
3. Choose platform/market if desired.
4. Click generate.
5. Review a generated set with simple labels.
6. Select, regenerate one image, or export.

Advanced inputs should be progressive:

1. product specs
2. target buyer
3. keywords
4. competitor reference
5. style reference
6. forbidden claims
7. required overlay text

Do not force the user through a long Amazon copywriting workflow unless they choose an advanced mode.

## Image Set Defaults

For `one_click_product_set`, default to:

| Slot | Purpose |
| --- | --- |
| Main image | Clear product-first image. |
| Feature image 1 | Strongest buyer benefit. |
| Feature image 2 | Material/detail/function proof. |
| Scenario image | Product in realistic use context. |
| Size/spec image | Scale, dimensions, or compatibility when relevant. |
| Trust/comparison image | Quality proof, difference, package, or warranty-safe trust cue. |
| Ad cover | Campaign-style hero for traffic acquisition. |

The pack may reduce or expand the count depending on product category, platform, and user plan.

## Development Sequence

### E0 - Manifest And Placeholder Activation

1. Add e-commerce package and manifest.
2. Register it as inactive/beta until required contracts and tests exist.
3. Keep existing `EcommerceAgentFamily` as a vertical refinement layer.
4. Add tests for manifest and inactive behavior.

### E1 - Product Input And ProductTruthLock

1. Use AssetRoleAnalyzer to identify product/reference assets.
2. Build ProductTruthLock from image analysis and user text.
3. Let the user or API correct product facts later.
4. Add tests for immutable fact preservation.

### E2 - Commerce Brief

1. Build CommerceIntelligenceBrief from product truth, prompt, and optional platform.
2. Accept optional keywords/competitor/listing data.
3. Do not require external web scraping in the first implementation.
4. Add tests for ranked selling points and unsupported claim warnings.

### E3 - Image Set Planner

1. Convert commerce brief into EcommerceAssetRecipes.
2. Map each selling point to one output image.
3. Apply MarketplaceRuleProfile.
4. Add tests for default image sequence and platform-specific slot differences.

### E4 - Prompt/Layout/Evaluation Integration

1. Use shared PromptConstraintCompiler.
2. Use existing central brain loop.
3. Add CommerceCritic to evaluation/refinement.
4. Keep provider routing unchanged.
5. Add golden tests for mature product sets.

### E5 - Export Packaging

1. Add platform-aware export package metadata.
2. Include image slots, dimensions, naming, review status, and suggested overlay copy.
3. Add tests for export record creation.

## Reuse Of Existing `EcommerceAgentFamily`

The current `app/vertical_agents/ecommerce_pack.py` should not be deleted.

Use it as:

1. a refinement hook inside the central brain
2. a lightweight fallback for e-commerce-like requests
3. a bridge while the full Scenario Pack is being implemented

But move heavy commerce logic into:

`app/scenario_packs/ecommerce/`

and shared reusable logic into:

`app/shared_capabilities/`

## Required Tests

1. E-Commerce Scenario Pack registration.
2. Default mode is `one_click_product_set`.
3. Product image upload produces ProductTruthLock.
4. ProductTruthLock prevents shape/material/logo changes in generated constraints.
5. Commerce brief ranks selling points.
6. Image set planner creates appropriate slots.
7. Marketplace profile changes slot rules without changing central brain.
8. Prompt constraints include product truth and selling point obligations.
9. CommerceCritic flags missing product visibility or unsupported claims.
10. Export packager creates platform-aware package metadata.
11. General Creative remains unaffected.
12. Low-level provider controls remain rejected.

## Final Acceptance

The E-Commerce Scenario Pack is complete enough when:

1. A beginner can upload product image + simple prompt and receive a coherent product image set.
2. Each image has a clear business purpose.
3. The set preserves product truth.
4. The set uses selling points, buyer intent, and platform expectations.
5. The user can regenerate one slot without restarting the whole job.
6. Export metadata is usable by the front end.
7. Existing General Creative and V3 core tests still pass.
