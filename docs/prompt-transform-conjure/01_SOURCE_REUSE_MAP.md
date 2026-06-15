# Source Reuse Map

This file tells Codex which public source files in `kadevin/ilab-gpt-conjure` should be inspected before implementation.

Reference repo:

https://github.com/kadevin/ilab-gpt-conjure

---

## 1. Prompt Guard Source

File:

`codex_image/prompt_guard.py`

Reuse targets:

- `extract_prompt_constraints(prompt)`
- `build_prompt_guard_instructions(constraints)`
- `build_original_prompt_instructions()`
- `build_guarded_prompt(prompt, instructions)`

Usage in Alchemy V2:

- Extract hard constraints from user prompt and V2 prompt.
- Build preservation text for stable/enhanced mode.
- Wrap final prompt when the downstream image provider has no separate instruction channel.

---

## 2. Prompt Fidelity Routing Source

File:

`codex_image/webui/executor_transport.py`

Reuse targets:

- `PROMPT_FIDELITY_MODES`
- `DEFAULT_PROMPT_FIDELITY`
- `_normalize_prompt_fidelity(value)`
- `_prompt_for_transport(...)`
- `_instructions_for_transport(...)`

Usage in Alchemy V2:

- Map V2 modes to fidelity behavior.
- Decide whether to keep prompt unchanged or add preservation text.
- Keep provider transport handling explicit.

---

## 3. Runtime Application Source

File:

`codex_image/webui/executor.py`

Reuse targets:

- read prompt fidelity from task params
- build guard text before provider call
- pass final prompt to image client
- save revised prompt in output metadata

Usage in Alchemy V2:

- Insert transform before safety check.
- Preserve original prompt in metadata.
- Store final prompt sent to provider.

---

## 4. Prompt Template Source

File:

`codex_image/webui/prompt_templates.py`

Reuse targets:

- template category defaults
- template mode validation
- template normalization
- JSON import
- Markdown import
- variable extraction with `{{ variable }}`

Usage in Alchemy V2:

- Optional future template-pack import.
- Useful when importing prompt packs similar to GPT-image-2 prompt collections.

---

## 5. Provider Payload Source

Files:

- `codex_image/client_types.py`
- `codex_image/openai_images_client.py`
- `codex_image/codex_responses_client.py`

Reuse targets:

- default image model constants
- image result shape
- revised prompt capture
- Images API payload building
- Responses-style payload building

Usage in Alchemy V2:

- Keep final prompt and provider payload traceable.
- Capture provider revised prompt where available.

---

## 6. What Not To Search For

The public reference source does not expose a standalone LLM expand/rewrite/refine chain.

Do not spend implementation time looking for hidden code for that behavior.

If V2 needs creative rewriting later, create it as a V2-native extension and document it separately.
