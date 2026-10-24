# RB06 native options core

## Objective and bounded phase

The total objective remains an explicitly selected Bridge path through Alchemy's
canonical frozen plan, native persistence and shared review. This phase adds
configured `codex-image` and `midjourney-manual` development profiles beside
`fake-image`, without claiming real account, renderer, visual quality or billing
acceptance. This is an auxiliary adapter, not a foundation or template change.

Native enablement and a profile allowlist are independent gates. Planning binds
profile and PNG/JPEG format into server-owned identity before Brain is invoked.
Only auto quality, no fidelity/background/moderation/compression, one output and
the three existing sizes are admitted. Auto means unspecified tool quality;
format is verified on original returned bytes, not claimed tool parameter control.
Manual references are rejected before planning. Fake/Codex retain zero to two
authorized originals; canonical high fidelity is rejected, never rewritten.

Default fake/PNG plan IDs, checkpoint IDs and safe metadata remain compatible.
Native registration uses the same journal, receipt provider and review-only
continuation. Real development candidates are not marked mock but cannot become
formal delivery, selection or export. No default routing, global review policy,
checkpoint hook, automatic selection, billing or external provider calls change.

## Verification

Focused tests cover configured profiles, frozen options, identities and legacy
replay, original PNG/JPEG bytes and metadata, references, rejection, review-only
registration and checkpoint replay. All real-profile tests are protocol fixtures,
not real-tool acceptance. Host configuration/wire negotiation are coordinator
owned and must be integrated separately before this phase is considered complete.

## Core verification receipt

On 2026-10-21, the native facade/planning/registration/options selection passed
112 tests. One additional real-profile lost-plan-response test was then added;
the final options file passed all 35 tests (the existing native files contain
78 tests). Isolated mock-only runs used the established safe-environment wrapper.
Whitespace verification passed. No real provider, account or billing ran.

The additional minimal-UX, scenario/product-API, generic-export, MCP-resume and
review-timeout selection passed 138 tests and failed three existing Doc263 MCP
fixtures. An independent detached worktree at unchanged base `041ebd97` reproduced
all three failures: persisted-output projection accesses a fixture candidate with
no `is_mock`, and two submitted-reference resume fixtures end blocked instead of
their expected generated/finalizing state. No MCP code or fixtures were modified.
These baseline failures are separate from this core milestone, not a full-suite
green claim. Coordinator integration and actual HTTP acceptance remain required.


Integrated closure: host coordinator and actual HTTP acceptance are now complete;
see [RB06 integrated receipt](../../src_skeleton/app/integrations/render_bridge/docs/RB06_REAL_PROFILE_OPTIONS.md).
The three baseline Doc263 doubles described above were subsequently corrected in
a separate fixture-only commit: each now declares is_mock=False and asserts its
projection, without changing production code or weakening checkpoint/reference
assertions. All 73 tests in that MCP fixture file passed.
