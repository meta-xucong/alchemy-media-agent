# 06 Codex Task Prompt

Use this prompt when assigning the implementation to Codex.

---

You are implementing the V2 Prompt Transform Layer in `alchemy-media-agent`.

Read these docs first:

```text
docs/prompt-transform-conjure/00_ROOT_RULES.md
docs/prompt-transform-conjure/01_SOURCE_REUSE_MAP.md
docs/prompt-transform-conjure/02_CODE_STRUCTURE.md
docs/prompt-transform-conjure/03_IMPLEMENTATION_STEPS.md
docs/prompt-transform-conjure/04_API_CONTRACTS.md
docs/prompt-transform-conjure/05_TEST_PLAN.md
```

Reference repository:

```text
https://github.com/kadevin/ilab-gpt-conjure
```

Implementation rules:

1. Reuse/adapt source behavior from `ilab-gpt-conjure`.
2. Do not invent a hidden expand/rewrite/refine LLM algorithm.
3. Implement prompt fidelity, prompt guard, constraint extraction, and guarded transport prompt.
4. Integrate after V2 prompt plan creation and before provider generation.
5. Do not overwrite `ImagePromptPlan.prompt`.
6. Write final prompt to `ImagePromptPlan.user_variables["generation_prompt"]`.
7. Store transform metadata in `ImagePromptPlan.user_variables["prompt_transform"]`.
8. Add unit and integration tests.

Start with these files:

```text
custom_media_agent_2_0/app/services/prompt_transform/models.py
custom_media_agent_2_0/app/services/prompt_transform/guard.py
custom_media_agent_2_0/app/services/prompt_transform/modes.py
custom_media_agent_2_0/app/services/prompt_transform/transport.py
custom_media_agent_2_0/app/services/prompt_transform/transformer.py
custom_media_agent_2_0/app/services/prompt_transform/metadata.py
```

Then integrate into:

```text
custom_media_agent_2_0/app/services/generation.py
```

Run tests after implementation.
