# 01 Source Reuse Map

This document maps the public `kadevin/ilab-gpt-conjure` source code to the V2 Prompt Transform Layer in `alchemy-media-agent`.

This is a Codex implementation guide. It supersedes any older wording that described the reference project as having a hidden `expand -> rewrite -> refine` LLM chain.

## 1. Root Rule

Do not invent a hidden Conjure algorithm.

The reference repository is a GPT-image-2 image generation WebUI/workbench. The reusable value is visible in source code:

- prompt fidelity modes
- prompt guard instructions
- user constraint extraction
- original prompt preservation
- guarded prompt wrapping
- prompt template library
- prompt snippet library
- reference image and gallery input resolution
- OpenAI-compatible Images/Responses payload shaping
- provider execution metadata and revised-prompt capture

If a behavior is not present in the reference repository, implement it only as an Alchemy V2 extension and label it clearly.

## 2. Reference Source Files

Use these files from `kadevin/ilab-gpt-conjure` first:

```text
codex_image/prompt_guard.py
codex_image/webui/executor_transport.py
codex_image/webui/executor.py
codex_image/webui/executor_inputs.py
codex_image/webui/prompt_templates.py
codex_image/webui/prompt_snippets.py
codex_image/webui/schemas.py
codex_image/openai_images_client.py
codex_image/openai_responses_client.py
codex_image/client_types.py
```

## 3. Directly Reusable Behaviors

### 3.1 Prompt constraint extraction

Reference:

```text
codex_image/prompt_guard.py
- extract_prompt_constraints()
- _prompt_clauses()
- _is_title_font_constraint()
- _target_audience()
- _color_constraint()
- _limit_constraint()
- _dedupe()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/guard.py
```

Use this to preserve hard constraints such as:

- title/font constraints
- target audience
- color constraints
- required/prohibited/avoid instructions

### 3.2 Prompt guard instruction building

Reference:

```text
codex_image/prompt_guard.py
- build_prompt_guard_instructions()
- build_original_prompt_instructions()
- build_guarded_prompt()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/guard.py
custom_media_agent_2_0/app/services/prompt_transform/transport.py
```

Use this to implement Stable and Enhanced modes.

### 3.3 Prompt fidelity mode routing

Reference:

```text
codex_image/webui/executor_transport.py
- PROMPT_FIDELITY_MODES = {"strict", "original", "off"}
- DEFAULT_PROMPT_FIDELITY = "strict"
- _normalize_prompt_fidelity()
- _prompt_for_transport()
- _instructions_for_transport()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/modes.py
custom_media_agent_2_0/app/services/prompt_transform/transport.py
```

Alchemy-facing mode mapping:

```text
stable      -> original / minimal transformation
enhanced    -> strict / guarded transformation
exploration -> off + V2-native variant logic later
```

### 3.4 Prompt template management

Reference:

```text
codex_image/webui/prompt_templates.py
- PromptTemplateSettings
- _normalize_prompt_template_payload()
- _parse_prompt_template_import()
- _parse_prompt_template_json_import()
- _parse_prompt_template_markdown_import()
- _extract_prompt_template_variables()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/template_importer.py
```

Use this to import and normalize template packs, especially community prompt collections.

### 3.5 Prompt snippet management

Reference:

```text
codex_image/webui/prompt_snippets.py
- PromptSnippetSettings
- _normalize_prompt_snippet_payload()
- _clean_prompt_snippet_tag()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/snippets.py
```

Use this for reusable prompt fragments, not full templates.

### 3.6 Reference image and gallery input resolution

Reference:

```text
codex_image/webui/executor_inputs.py
- _file_to_data_url()
- _image_mime_type()
- _sniff_image_mime_type()
- _resolve_reference_assets()
- _resolve_gallery_refs()
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/prompt_transform/reference_inputs.py
```

This is optional for the first implementation because Alchemy already has uploaded asset support, but the mime detection and dedupe patterns are useful.

### 3.7 Provider prompt injection boundary

Reference:

```text
codex_image/webui/executor.py
- reads prompt
- reads prompt_for_model
- computes guard instructions
- builds transport_prompt
- passes prompt/instructions to image client
```

Alchemy target:

```text
custom_media_agent_2_0/app/services/generation.py
```

Alchemy already has a safe injection point because providers read:

```text
prompt_plan.user_variables["generation_prompt"] or prompt_plan.prompt
```

The transform layer should write final prompt into `generation_prompt` and keep `prompt_plan.prompt` as the original/template prompt.

## 4. License Handling

The reference repository declares AGPL-3.0-only.

Before copying source code directly:

1. Preserve attribution.
2. Confirm license compatibility with this repository.
3. If direct copy is not acceptable, implement behavior-compatible adapters based on public behavior and function signatures.

Codex should not silently vendor AGPL code without an explicit project decision.

## 5. What Not To Reuse Because It Does Not Exist

The reference source does not provide:

- hidden prompt scoring
- hidden image critic loop
- hidden visual planning
- hidden LLM expand/rewrite/refine chain
- hidden photography-specific optimizer

These can be added later as Alchemy-native features, but they are not part of the Conjure source reuse scope.
