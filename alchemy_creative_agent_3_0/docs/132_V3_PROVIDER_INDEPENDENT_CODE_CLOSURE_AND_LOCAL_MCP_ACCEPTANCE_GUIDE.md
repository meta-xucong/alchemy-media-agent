# Doc132: V3 Provider-Independent Code Closure And Local MCP Acceptance Guide

Status: active companion to Doc127. This document defines the fastest
complete acceptance route for **Alchemy-owned code** while the Web image
gateway or an upstream Provider is unavailable. It does not loosen Doc127's
real-pixel conditions for a production release.

## 1. Decision Boundary

```text
Alchemy responsibility
  = intent/reference admission -> remote Brain -> frozen plan/envelope
    -> constraint resolution -> canonical final Provider prompt
    -> project/job/browser lifecycle truth

Upstream responsibility
  = account routing -> transport -> provider-native request acceptance
    -> pixels -> upstream availability and timeout behavior
```

An upstream timeout, 4xx/5xx, quota, router choice, or response-format fault
does not reopen an otherwise green Alchemy code-closure result. Conversely,
an attractive locally generated image cannot conceal an Alchemy prompt,
reference, lifecycle, or UI defect.

There are two deliberately separate decisions:

| Decision | Evidence required | What it permits |
| --- | --- | --- |
| **Code closure** | offline regression, deterministic lifecycle/browser fixtures, and canonical Local MCP evidence | declare the affected Alchemy implementation complete; hand upstream failures to the Provider owner |
| **Production release** | Doc127 real Web Provider pixels, certifying review, restricted provenance, and human sign-off | enable the relevant Web template gate |

No team may call code closure a production pass, or call a Provider outage an
Alchemy code failure without a reproducible local/runtime defect.

## 2. Local MCP Is The General Visual Oracle

Doc130/131 Local MCP is the code-closure visual oracle for `general_template`:

```text
same shared Scenario Runtime + remote Central Brain + frozen envelope
-> same canonical Web Provider materializer
-> byte-identical final prompt and the same admitted reference paths
-> exactly one Codex built-in ImageGen call
```

It is valid only when the result records all of the following:

- `planned_for_codex_native_imagegen`;
- `llm_used=true` and `fallback_used=false`;
- the requested count exactly equals the returned plan count;
- the returned prompt hash is the canonical Provider prompt hash;
- declared/admitted reference counts and source hashes are visible; and
- one native ImageGen call per planned output, labelled
  `conversation_only_not_certified`.

Local MCP must remain opt-in, General-only, and conversation-only. It creates
no candidate, retry, review, artifact import, project delivery, Web fallback,
or production evidence. E-Commerce and Photography must remain blocked in
this interface rather than silently becoming General jobs.

## 3. Shared Code-Closure Baseline

Before a template owner starts its work, the mainline operator freezes a clean
`origin/main` commit and records:

```powershell
python -m pytest alchemy_creative_agent_3_0/tests -q
python -m compileall -q alchemy_creative_agent_3_0/app alchemy_creative_agent_3_0/tests
node --check src_skeleton/app/static/app.js
git diff --check
python -m pytest tests/test_doc130_codex_native_prompt_parity.py -q
```

The final command proves canonical Local MCP parity; it does not substitute
for the Web Provider. Any fixture must use the shared project, generation,
review, retry, and result-projection seams. A fixture may never introduce a
template-private provider, reviewer, selector, static creative recipe, prompt
stack, font/OCR/canvas path, or fake certified pixel verdict.

## 4. Mainline-Owned Browser and Lifecycle Closure

These checks require no Provider pixel and remain mandatory because they are
Alchemy product behavior.

| ID | Deterministic fixture/browser assertion | Pass condition |
| --- | --- | --- |
| M1 | upload/select a reference | its preview, role and binding survive create, refresh, reopen, and continuation preparation exactly once |
| M2 | seed a shared final-winner projection | recent-project card, detail page and refreshed/reopened page show the same final image without a stale spinner or empty result |
| M3 | seed blocked, failed, withheld/manual and metadata-only states | UI distinguishes each from success and exposes safe provenance; none is shown as a delivered image |
| M4 | project worker restart/finalization boundary | interrupted work reaches one honest terminal record; no silent replay or permanently `generating` job remains |
| M5 | General isolation | product words alone do not select E-Commerce; no Photography, platform, slot, or specialist continuation UI leaks into General |

M1 and M2 directly close the previously observed reference-thumbnail and
refresh-rehydration defects. Tests must cover both API projection and a real
browser fixture/DOM assertion.

## 5. E-Commerce Owner Work Package

The E-Commerce branch owns template/UI assertions only; it must not repair the
gateway, create a private rendering path, or revive static roles.

1. Rebase to the frozen main commit and retain the LLM-native correction.
2. Use a shared deterministic generation/result fixture to prove exact
   Brain-authored whole-image direction count and project aggregation for
   **N=1, 2, 4, and 7**.
3. Prove new forward surfaces contain only opaque output bindings and exactly
   N directions: no `slot`, recipe, suite, default preset, overlay, static
   camera/crop/scene instruction, or default sales copy enters Brain,
   envelope, Provider materialization, ordinary delivery, or browser UI.
4. Complete the already-scoped legacy copy cleanup so the browser describes
   LLM-created whole-image directions rather than fixed main/selling/scene/
   trust-image promises. Historical identifiers may be read only.
5. Fixture-test refresh/reopen, child continuation history, wrong-count Brain
   block, and held/blocked delivery truth without calling an upstream.

The owner may use Local MCP only for a General comparison of the shared
materializer. It must not use it to render an E-Commerce job or claim Gate C
or Gate D.

## 6. Photography Owner Work Package

The Photography branch owns template structural contracts and their public
projection; it must not add a Photography Provider/reviewer/retry path.

1. Rebase to the frozen main commit and preserve remote-Brain fail-closed
   behavior.
2. Exercise `single_hero` and `professional_set` through the shared
   deterministic generation/result fixture. A professional set must freeze
   and project exactly these lineage roles:

   ```text
   session_hero, environmental_context, detail_or_moment
   ```

3. Prove each role independently reaches a terminal state, retains
   append-only history, and contributes exactly one current final winner or a
   diagnosable held/blocked entry. It may never silently collapse to one
   image.
4. Browser-test template selection, refresh/reopen, project summary and role
   aggregation; retain explicit named-profile reconfirmation and nonhuman
   high-fidelity identity blocking.
5. Prove `metadata_only`/manual confirmation cannot be projected as a P10
   success or automatic delivery.

Local MCP remains unavailable to Photography by design. If a future request
needs a local visual renderer for a frozen Photography plan, it requires a new
mainline contract that relays the *already frozen* template plan unchanged;
it may not replan or downgrade through General.

## 7. Evidence and Verdict Rules

Each owner supplies a small redacted code-closure record containing only:

```text
commit, test commands/results, fixture IDs, browser steps/screenshots,
template/scenario, requested count, expected/observed terminal state,
prompt/reference hash where Local MCP was used, and remaining external holds.
```

Do not commit customer media, full prompts, credentials, endpoint details,
provider account/line identities, raw responses, or generated media.

Use these labels exactly:

- `code_closure_passed`: all applicable Alchemy-owned tests and fixtures pass;
- `upstream_hold`: no-pixel Provider/gateway outcome; no Alchemy defect implied;
- `production_gate_pending`: real Web Provider/review evidence is still absent;
- `code_defect`: reproducible contract, lifecycle, prompt, reference, or UI
  failure; fix it before declaring code closure.

## 8. Parallel Execution and Mainline Integration

```text
mainline: Doc132 + M1-M5 + common regression + integration
    |-- E-Commerce: Section 5 fixture/UI package
    `-- Photography: Section 6 fixture/UI package

MCP专用: General-only visual checks on the exact shared prompt/reference path
```

Every worker uses a dedicated worktree and branch. The mainline integrator is
the only writer to `main`. Each branch must rebase onto the current main, run
focused tests, then provide commit, changed-file list, test results and the
closure label. Mainline reviews one branch at a time, re-runs affected tests
and the full V3 suite, then pushes a small verified integration commit.

## 9. Completion Rules

**Alchemy code closure is complete** when M1-M5, Sections 5 and 6, shared
regression, and the relevant Local MCP General T2I/reference evidence are
green on one clean main commit. At that point, remaining Provider 4xx/5xx,
timeouts, routing and real-pixel review availability are `upstream_hold`, not
reasons to continue altering Alchemy.

**Production release remains governed by Doc127.** Its Web Provider and
real-pixel review gates may be resumed only when the upstream owner reports a
healthy route. No production flag changes as part of this document.
