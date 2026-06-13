# Conjure Integration - Root Development Rules (Codex Ready)

This document defines the development rules for integrating a Conjure-style Prompt Transformation Layer into V2.

---

# 1. Core Principle

The transformation layer should be designed with reference to:

https://github.com/kadevin/ilab-gpt-conjure

All implementation should stay consistent with the behavior and structure of that repository.

---

# 2. Reuse Principle

Codex should prioritize reusing existing transformation patterns where possible:

- expand step logic
- rewrite step logic
- refine step logic
- normalize step logic

If equivalent logic exists in the reference repository, it should be adapted rather than re-implemented from scratch.

---

# 3. System Boundary

V2 Responsibilities:
- intent understanding
- template selection
- base prompt generation

Conjure Layer Responsibilities:
- prompt transformation only
- no intent parsing
- no scene planning

---

# 4. Architecture Constraint

```
V2 → Base Prompt → Conjure Transform → Final Prompt → Image Model
```

This pipeline must remain strictly separated.

---

# 5. Implementation Guidance

- Do not merge V2 logic into transformation layer
- Do not alter transformation order without necessity
- Keep transformation steps modular

---

# 6. Reference Source

All transformation behavior should align with the ilab-gpt-conjure repository:

https://github.com/kadevin/ilab-gpt-conjure

---

# 7. Final Rule

Transformation layer should behave as a post-processing system for prompts, not a generator.
