# 171 V3 Protected User Intent Semantic Integrity Closure

Status: implemented and accepted on the controlled Local MCP/ImageGen path.

## 1. Purpose

Doc171 closes the remaining generic prompt-authority defect found after the
Human Realism and developmental-stage work was audited for overfitting.

The defect was not a child, teenager, complexion, studio, or portrait recipe.
The full protected request already reached the Remote Brain. During a later
whole-prompt rewrite, however, the Brain could replace an explicit static studio
scene and neutral light with a more narrative window or lifestyle scene while
trying to make the person feel less generic.

This is semantic drift. It must be fixed at the final Brain-authoring boundary,
not by adding local keyword checks or appending more renderer prose.

## 2. Governing invariant

```text
Protected user intent is the immutable semantic source.

Every explicit, non-conflicting current-request choice and exclusion must
survive finalization with semantically equivalent meaning.

Compatible creative detail may clarify that meaning. It may not replace the
requested subject, scene, light, camera, mood, expression, complexion,
wardrobe, or format with a different creative direction.
```

A static studio capture is already a complete situation. Human Naturalness may
make the person individually present inside that capture; it must not invent a
window, action, location, or lifestyle narrative merely to satisfy personhood.

## 3. Architecture boundary

Doc171 does not add:

- an age-specific or demographic branch;
- a studio-scene branch;
- a field-by-field local prompt validator;
- keyword, regex, or phrase-count matching;
- a new receipt or a third Brain call;
- a local prompt suffix, negative list, or repair template;
- a new Provider, reviewer, retry loop, or template capability.

It reuses the existing protected user intent, frozen ownership ledger,
CapabilityExecutionEnvelope, Human Naturalness decision, and complete-prompt
Remote Brain finalization.

## 4. Final rewrite semantics

When a candidate prompt is reconsidered, it is non-authoritative only where it
conflicts with a frozen obligation. The protected user intent remains
authoritative throughout the rewrite.

The Brain must compare complete meanings rather than tokens. If the candidate
has drifted, it rewrites the whole prompt to restore the protected meaning while
still resolving active shared capabilities holistically. It must not expose an
internal checklist or turn the protected request into a structured word stack.

The same rule applies to all ages, people, products, scenes, lighting styles,
complexions, templates, and reference ownership combinations.

## 5. Historical document hygiene

Doc77 and Doc78 contain older named demographic complexion examples. Doc94 and
Doc159 already supersede them as runtime authorities. Their new correction
notes make explicit that those examples are historical validation context only
and must not activate or word a fresh runtime prompt.

## 6. Acceptance

Implementation acceptance requires:

1. A drifted finalization candidate is given together with a protected request
   for a different explicit scene and light.
2. The Remote Brain contract requires semantic equivalence to the protected
   meaning and treats the requested static scene as complete.
3. The implementation contains no local scene, age, complexion, or demographic
   recipe and no keyword/regex prompt enforcement.
4. Six-year-old, fifteen-year-old, and adult control requests use the same
   shared semantic authority and do not inherit each other's rendering goals.
5. A real fifteen-year-old control request preserves its explicit studio,
   lighting, complexion, age, and format choices in the canonical prompt.
6. A real generated image materially follows that canonical prompt.
7. Focused and full V3 regression suites pass.

The real control run also exposed an age-sensitive safety residue: the Brain
invented an aesthetic comment about a young person's figure even though the
user requested only an ordinary fully clothed portrait. Shared Brain safety now
forbids introducing unrequested emphasis on body shape, physical development,
sensuality, or bodily attractiveness in any age-sensitive request. This is a
generic semantic safety boundary, not a child-scene prompt recipe.

## 7. Non-claims

Doc171 does not claim that every stochastic image will be aesthetically ideal.
It certifies that Alchemy's final Brain-authored renderer instruction preserves
the user's meaning without restoring brittle local prompt engineering. Pixel
quality remains governed by shared review, bounded retry, and final delivery.

## 8. Controlled evidence

The first fresh fifteen-year-old control plan preserved the requested age,
white studio, neutral daylight and neutral complexion, but the Brain invented
an unnecessary aesthetic comment about the young person's figure. Codex
ImageGen rejected that prompt at input moderation. The shared age-sensitive
semantic safety boundary was corrected rather than deleting a word at the host.

The second fresh plan produced canonical prompt SHA-256:

```text
d77052949966a4db2729cd4d6810e88597f92e0e638623703260fcb9be4934cb
```

It retained the requested fifteen-year-old stage, pure-white seamless studio,
neutral daylight, scene-neutral complexion, ordinary complete clothing and
vertical composition. It contained no body-shape aestheticization, child-stage
recipe, cold-fair default, demographic complexion inference or local repair.
Codex built-in ImageGen accepted the exact prompt and produced a clean studio
portrait. Human inspection found a coherent adolescent rather than a six-year-
old child or an adult, neutral skin color, natural non-presentational affect,
clean white capture and no visible policy or rendering defect.

Verification:

- Doc171 and affected shared authority/parity suite: 89 passed.
- Complete V3 suite: 990 passed, two existing FastAPI deprecation warnings.
- Repository-level suite: 201 passed, the same two warnings.
- Compileall, browser JavaScript syntax, Local MCP plugin validation and
  `git diff --check`: passed.
