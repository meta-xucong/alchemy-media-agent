# Doc118 Phase N1 Implementation Plan

## Scope

This change implements the Doc118 planning-only boundary:

```text
explicit Codex Native ImageGen choice
-> local stdio MCP prompt planning
-> Codex built-in image tool once per frozen output
-> conversation-only, non-certified result
```

It is foundation planning work plus a separately installed plugin surface.  It
does not alter Web Mode, a Web Provider, General's scenario-neutral semantics,
or specialized-template ownership.

## Milestones

1. Add a red contract test for the absent native planner, commit it, and record
   the expected import failure.
2. Replace the active sidecar with a native planning-only contract and facade.
   The facade accepts only user input, explicit template, requested count/size,
   and declared in-conversation reference channels.  It builds all V3 internal
   envelopes itself and calls `ScenarioRuntime.plan_job()`, never
   `generate_job()`.
3. Inject a planning-only generation-router sentinel so the planner cannot
   construct or use a production image provider.  The sentinel raises if any
   generation path reaches it.
4. Remove the retired B2 renderer, materialization/import, candidate/delivery,
   key-file, and render-tool surfaces from the active adapter.  Do not retain a
   compatibility namespace or hidden fallback.
5. Return public-safe, exact-count prompt records with frozen role lineage,
   constraints, text policy, reference instructions, and conversation-only
   provenance.  Keep no image bytes, paths, candidate IDs, review state, or
   delivery records.
6. General is enabled first.  E-Commerce and Photography only pass through
   their existing template/remote-Brain/role/reference gates; any unavailable
   or mismatched condition returns `blocked` without General fallback.
7. Replace B2 tests with native negative-boundary and isolation regressions,
   then validate the plugin manifest and stdio MCP surface.

## Acceptance Evidence

- `tools/list` exposes only `prepare_native_imagegen_plan`.
- The public input schema has no job IDs, paths, provider metadata, raw
  envelope, API configuration, or hidden recipe fields.
- General returns exactly the requested count of prompt-only records.
- No API, Web Provider, browser/session/cache, artifact import, candidate,
  review, retry, final-delivery, or CLI-control path exists in the active
  sidecar.
- Every successful plan carries
  `execution_channel=codex_native_imagegen`,
  `renderer=codex_builtin_imagegen`, and
  `delivery_state=conversation_only_not_certified`.
- The result is planning evidence only; it is not evidence for any Provider or
  specialized-template production gate.
