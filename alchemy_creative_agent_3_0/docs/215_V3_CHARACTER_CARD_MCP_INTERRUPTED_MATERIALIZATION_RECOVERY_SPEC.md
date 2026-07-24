# Doc215 — V3 Character Card MCP Interrupted Materialization Recovery

## Status

Implemented as a narrow recovery contract for Professional Character Card MCP
validation. This document supersedes any interpretation that a failed or
interrupted MCP validation run may be recovered by opening a new candidate,
reusing an old consumed handoff, or changing prompt, aesthetics, Vision gates,
or framing thresholds.

## Evidence that triggered this spec

Fresh `expression.laugh` validation after Doc214 produced a Product API job:

- job: `job_0224fe0d2f`
- stage: `expression_set`
- slot: `expression.laugh`
- attempt round: `5`
- channel: `mcp`
- operation: `visual_asset_a0a2aee719e8474c:expression_set:expression.laugh:1:round5`

The job had a persisted `planning_result` and a Doc214-compliant canonical
character-card framing direction, but had no `generation_result`, no
`mcp_materialization` metadata, no matching handoff record for that operation,
and no shared Vision receipt. No validation process remained active. The
validation event log contained `stage_prepare_start` but no
`stage_prepare_result`.

This proves the failure layer was not laugh quality, policy rejection, or a
missing final prompt. It was an interrupted Product API → Provider/MCP
materialization boundary after planning and before handoff creation.

## Authoritative behavior

Professional Character Card MCP recovery has three distinct checkpoints:

1. `mcp_materialization_pending`: a frozen handoff exists and must be resumed
   by submitting/consuming that exact handoff.
2. `mcp_review_pending`: an artifact/output exists and must be resumed through
   shared review/finalization.
3. `interrupted_before_handoff`: the Product API job is still `generating`, has
   a `planning_result`, has no `generation_result`, and has no
   `mcp_materialization` handoff metadata.

Only checkpoint 3 is covered by Doc215.

## Recovery contract

When the Host sees a Character Card MCP job for the exact same operation in
checkpoint 3, it may re-enter the same job with an internal metadata flag:

`_v3_resume_interrupted_mcp_materialization=true`

This is not an automatic retry and not a new candidate. It is a continuation of
the same server-owned operation. It must:

- keep the same job id and operation id;
- go through the same Product API `generate_job` path;
- go through the same Provider/MCP materializer;
- create or consume the ordinary MCP handoff;
- continue into the same shared Vision and Character Card slot gates;
- preserve prompt/reference parity;
- not alter prompt wording, aesthetics, laugh gates, framing floors, reference
  budgets, or retry budgets.

## Fail-closed boundaries

The interrupted-job reentry flag is accepted only when all of the following are
true:

- job status is `generating`;
- `planning_result` exists;
- `generation_result` is absent;
- generation channel is `mcp`;
- operation id exists;
- no `mcp_materialization` handoff metadata exists;
- the job is a trusted Professional Character Card or Anchor Pack preparation
  job;
- no active background generation attempt id is present.

If a handoff exists, existing handoff resume is authoritative. If an output
exists, shared review/finalization is authoritative. If the job is ordinary
Standard/General/E-Commerce/Photography work, Doc215 does not apply.

## Tests

Doc215 is covered in `test_v3_doc203_mcp_handoff_resume.py`:

- Product API accepts only the pre-handoff MCP interruption shape;
- Character Card Host re-enters the same interrupted job without replanning;
- an existing MCP handoff still uses normal handoff resume and never receives
  the interrupted-job reentry flag.
