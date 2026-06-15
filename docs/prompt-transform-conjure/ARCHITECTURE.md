# Architecture - Conjure Prompt Enhancement Layer

This document supersedes the earlier generic expand/rewrite/refine wording.

The implementation scope is now source-backed by the public `kadevin/ilab-gpt-conjure` repository.

---

## 1. Target Flow

Current V2 flow:

`compose_prompt_plan -> safety_check -> create_image_job`

Target V2 flow:

`compose_prompt_plan -> apply_conjure_prompt_transform -> safety_check -> create_image_job`

The transform runs before safety so the final provider prompt is the one being checked.

---

## 2. Source-Backed Capabilities

The public Conjure source supports these reusable behaviors:

1. Prompt constraint extraction.
2. Prompt preservation text.
3. Original prompt preservation mode.
4. Guarded prompt wrapping.
5. Prompt fidelity routing.
6. Prompt template import and normalization.
7. Provider payload shape and revised prompt capture.

Reference files:

- `codex_image/prompt_guard.py`
- `codex_image/webui/executor_transport.py`
- `codex_image/webui/executor.py`
- `codex_image/webui/prompt_templates.py`
- `codex_image/client_types.py`
- `codex_image/openai_images_client.py`
- `codex_image/codex_responses_client.py`

---

## 3. Three Modes

### stable

Preserve current V2 prompt and template structure. Use for template-sensitive runs.

### enhanced

Extract constraints and add preservation behavior before provider submission.

### exploration

Reserved for future V2-native variants. It can initially fall back to enhanced.

---

## 4. V2 Boundary

V2 continues to own:

- intent understanding
- case/template retrieval
- Template Lock
- Visual Grammar Lock
- ImagePromptPlan construction
- safety
- provider job creation

Conjure layer owns only:

- prompt constraint extraction
- prompt fidelity routing
- provider-safe prompt preservation
- metadata recording

---

## 5. Metadata

Store metadata in:

`ImagePromptPlan.user_variables["conjure_transform"]`

Fields:

- enabled
- mode
- source_repo
- base_prompt
- final_prompt
- constraints
- transport_kind
- guard_applied
- warnings

---

## 6. First Implementation Scope

Implement:

- package skeleton
- stable mode
- enhanced mode
- source guard adapter
- fidelity adapter
- integration before safety
- tests

Defer:

- exploration variants
- extra LLM rewriting
- scoring
- image review feedback
