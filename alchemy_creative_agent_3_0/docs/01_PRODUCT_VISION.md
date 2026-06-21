# 01 Product Vision

## 1. Product Name

Working name:

```text
Alchemy Creative Agent 3.0
```

Product concept:

```text
A natural-language-first AI commercial visual production agent.
```

Strategic positioning:

```text
Not a design tool.
Not a canvas editor.
Not a node workflow system.
Not a prompt playground.

It is an AI commercial visual production system for users who do not understand design or AI.
```

## 2. Lovart Benchmark

Lovart-like products are strong because they behave like AI design agents rather than simple image generators.

They can coordinate multiple creative decisions:

- concept direction
- brand asset generation
- style consistency
- layout decisions
- image generation
- refinement
- export-ready asset production

Alchemy Creative Agent 3.0 should benchmark this level of output quality and consistency, but with a different product philosophy.

Lovart-like direction:

```text
AI design workstation
```

Alchemy 3.0 direction:

```text
AI commercial visual production agent
```

The difference is important.

Lovart may still require users to understand creative direction, choose assets, operate design flows, or review multi-step visual workflows.

Alchemy 3.0 should hide the workflow and let agents operate internally.

## 3. Target Users

The primary users are non-design, non-technical commercial operators.

Examples:

- small restaurant owners
- milk tea shop owners
- barbecue shops
- hotpot restaurants
- bakeries
- homestays
- beauty salons
- nail salons
- local service merchants
- individual e-commerce sellers
- small private-domain sellers
- livestream sellers
- personal brand operators

Assumptions about these users:

- They may not know what prompt engineering is.
- They may not know what style reference means.
- They may not know what aspect ratio is.
- They may not know how to use Photoshop, Figma, Canva, ComfyUI, or professional design tools.
- They may only have a phone.
- They may only know their business goal, not the design method.

Therefore, the product must accept rough business intent and turn it into commercial design output automatically.

## 4. Core User Promise

The product promise:

```text
Say what you need. Alchemy creates a brand-consistent commercial visual series for you.
```

Example:

```text
User input:
“帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。”
```

Expected output:

```text
- 4:5 Xiaohongshu cover
- 1:1 delivery platform product image
- 3:4 WeChat Moments poster
- 16:9 store screen image
- shared visual style
- consistent colors
- consistent typography direction
- consistent commercial tone
- reusable brand profile
```

The user should not need to manually select models, prompts, seeds, samplers, LoRAs, ControlNet maps, or workflow nodes.

## 5. Product Differentiation

### 5.1 Simpler Than Lovart

Alchemy 3.0 should be simpler because it does not ask the user to become a designer.

The product should not expose the full workflow unless the user explicitly wants advanced controls later.

Default mode:

```text
one natural-language input → generated commercial asset series
```

### 5.2 More Vertical Than Lovart

Lovart-like tools are broad design platforms.

Alchemy 3.0 should focus on high-frequency commercial visual scenarios:

- local restaurant promotion
- delivery platform product images
- Xiaohongshu covers
- WeChat Moments posters
- e-commerce product images
- festival promotion posters
- service package posters
- store announcement images
- group-buying images
- small brand campaign sets

The system should understand domain-specific rules, for example:

- food images must look appetizing but clean
- promotion images must highlight product and offer
- delivery images must be clear at small size
- Xiaohongshu covers need stronger click appeal
- local business posters should not look too abstract
- Chinese text must be accurate and readable

### 5.3 Stronger in Chinese Commercial Visuals

A key opportunity is Chinese commercial posters and platform-specific assets.

Instead of forcing the image model to render all text, Alchemy 3.0 should separate:

```text
visual image generation
+
accurate HTML / SVG / Canvas text rendering
```

This can produce better Chinese text accuracy, better price accuracy, and more editable commercial outputs.

### 5.4 Brand Consistency as a Core Feature

The product must not generate isolated beautiful images only.

It must build and reuse:

- brand memory
- style profile
- color palette
- visual tone
- layout preference
- successful prior results
- user choices
- product references

The output should feel like one brand across multiple assets.

## 6. Primary Use Cases

### 6.1 One-Shot Campaign Series

Input:

```text
“帮我做一个烧烤店夜宵促销图，适合朋友圈和美团。”
```

Output:

```text
- main poster
- group-buying image
- WeChat image
- delivery cover
```

### 6.2 Brand Style Establishment

Input:

```text
“我开了一家新奶茶店，想要清爽、年轻、干净的品牌视觉。”
```

Output:

```text
- brand style profile
- brand color suggestion
- sample poster
- product image style
- social media cover
```

### 6.3 Existing Brand Continuation

Input:

```text
“沿用上次的风格，帮我做端午节活动图。”
```

Output:

```text
- new festival campaign assets
- same brand colors
- same visual tone
- adapted holiday elements
```

### 6.4 E-Commerce Product Image Pack

Input:

```text
“帮我做一组蓝牙耳机淘宝主图，要科技感、干净、适合点击。”
```

Output:

```text
- main product image
- feature highlight image
- comparison image
- promotion banner
```

### 6.5 Local Service Promotion

Input:

```text
“帮我做一个美甲店开业优惠图，适合小红书和朋友圈。”
```

Output:

```text
- Xiaohongshu cover
- WeChat poster
- price package image
- store-opening announcement
```

## 7. Product Modes

### 7.1 Default Mode: Auto Commercial Series

The default mode should produce a small asset series automatically.

The user only provides natural language.

### 7.2 Brand Continuation Mode

Use existing brand memory and previous selected assets to generate new content.

### 7.3 Template-Matched Mode

The system may automatically choose a case template or allow the user to choose one manually.

The template should guide structure, not constrain the system into copying blindly.

### 7.4 Single Image Mode

For simple requests, the system may generate one image, but still through the same planning and scoring pipeline.

### 7.5 Advanced Mode Later

Later versions may expose controlled options such as:

- platform
- style intensity
- reference image strength
- number of candidates
- text layout preference

But these must remain optional.

## 8. Output Requirements

Each completed job should output:

```text
1. final images
2. asset names
3. intended platform
4. aspect ratio
5. commercial purpose
6. final text content
7. generation summary
8. brand consistency notes
9. reusable brand profile update
10. metadata manifest
```

## 9. Non-Goals

V3 should not initially build:

- a professional canvas editor
- a node workflow UI
- video generation
- timeline editing
- multi-user collaboration
- complex manual parameter panels
- direct ComfyUI-style graph editing

These may be useful later, but they are not part of the V3 foundation.

## 10. Product Success Criteria

V3 is successful if a non-design user can input one rough sentence and receive a usable visual asset series that:

- looks commercial
- is internally consistent
- fits the target industry
- fits the target platform
- contains accurate text when text is required
- preserves brand style across multiple outputs
- requires minimal user correction
- can be regenerated or continued later using brand memory