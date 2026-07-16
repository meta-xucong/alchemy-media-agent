# Doc146 — Doc144 Controlled Blue-Dress Acceptance Record

## Scope and status

This is the first controlled functional acceptance of Doc144's shared Human
Realism approval refinement. It uses the same user-authorized blue-dress
product reference as the prior regression and the Local MCP relay. The result
is a **provider-independent code/creative acceptance** under the current
acceptance policy: a successful relay confirms that Alchemy's frozen plan,
reference handling, canonical prompt, and Human Realism re-signing path work
together. It does not replace a Web Provider production Gate or convert the
conversation-only image into a persistent V3 delivery.

## Verified route

```text
authorized product reference
  -> General / shared capability activation
  -> remote Central Brain plan
  -> canonical provider-prompt finalization
  -> independent Human Realism re-sign
  -> Local MCP relay with byte-identical prompt/reference contract
  -> one Codex ImageGen comparison image
```

The planned run had exactly one output and one requested reference source. Its
admitted runtime representation preserved the source and its product-truth
crop. The final canonical prompt SHA-256 was
`899772086181509b108556de639e0e0440e93289b6941e139670bf17e77e0c0e`.

The remote Brain completed both required signing stages:

- `provider_prompt_finalize`
- `provider_prompt_human_naturalness_resign`

The Human Realism re-sign returned `rewritten`, not an automatic approval.
This is the desired Doc144 behavior: the remote Brain authored a complete
non-default whole-image direction itself. No local text, negative prompt,
keyword classifier, face rule, children/apparel branch, template-specific
recipe, or Provider retry wording was added.

## Visual observation

The resulting image retains the pale-blue dress, ruffled sleeves and front
illustration while presenting a school-age East Asian child with a sideward,
situation-owned look rather than the earlier generic commercial smile. The
lower face, eyes, hands, hair movement, light and depth are coherent at normal
inspection; the face reads as photographic rather than cartoon-styled. Skin is
substantially more camera-like than the earlier oily/painterly adult concern,
though it remains a little cleaner and smoother than a demanding real-world
editorial close-up. The skirt's rendered length/proportion is also somewhat
less faithful than the source garment.

These two observations are quality headroom, not a permission to add a narrow
child, garment or facial-feature heuristic. Any future work must remain a
shared, Brain-owned Human Realism improvement and prove benefit across
materially different people scenes.

## Safety and limits

- The Local MCP call was `conversation_only_not_certified`: it created no V3
  Project/Job/Candidate, shared review/retry history, final delivery, or Web
  Provider record.
- This record does not claim shared vision-model/hybrid pixel certification,
  Web Provider availability, Gate C/D completion, or production enablement.
- Doc145's empty/malformed JSON recovery did not construct a prompt locally.
  It only allowed the same remote Brain one re-answer before normal contract
  validation and the same two signing stages.

## Regression evidence

- Focused Brain/Human Realism/Local MCP coverage: `53 passed` after the final
  empty-response recovery change.
- Complete V3 suite: `782 passed`, with only two existing FastAPI deprecation
  warnings. It was executed in file/node groups because this Windows command
  host cuts off a single long pytest process before its final summary.
- Local MCP canonical prompt/reference and specialist relay suite:
  `33 passed`.
- `compileall`, `node --check`, `git diff --check`, and long-run state
  validation passed.

## Acceptance decision

Doc144's current shared capability revision is accepted for the stated
provider-independent functional comparison. The next optional quality phase is
not a patch against this blue-dress example: it must evaluate the remaining
skin-material and garment-proportion headroom across an adult portrait,
person/object interaction, low-key person scene, and this young-person
regression before proposing any universal change.
