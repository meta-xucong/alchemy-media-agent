# PR32 V3 Planned Job Drain Fence

## Objective and observed mismatch

The guarded cutover must stop work that can still be executing or waiting in
the current V3 process. It must preserve durable V3 records and must not
interrupt a generation attempt after it has claimed the job or started provider
work. The current inventory counts every
`planned` job as active, including plans created before the currently running
V3 container started. Those records cannot still be queued in that process,
but they remain unchanged in the shared storage root, so the guard can block
every future cutover indefinitely.

On the VPS, two `planned` records were created on 2026-09-29. They have no
background-generation attempt marker, no generation result, and no project
association. The active V3 container started on 2026-10-10. The guarded
activation stopped before maintenance, backup, or service mutation because it
counted those two records as active.

## Authority and correction model

- A nonterminal durable status remains evidence that a record must be
  preserved, but by itself does not prove work is executing in the current
  process.
- A `planned` job created at or after the current V3 container start is
  conservatively treated as active: it may still be queued in that process.
- A `planned` job with no project association, created before the current V3
  container start and with no background-generation attempt marker is a
  preserved resumable Product API plan, not active work. It is reported
  separately and its file is not changed. A project-associated plan remains
  blocking because project generation can be held in the current process's
  in-memory executor queue before the durable worker claim is written. The
  canonical ProductJob storage shape is `request.metadata.project_id`; the
  guard also recognizes the legacy top-level `project_id` field.
- A `planned` job with a background-generation attempt marker remains active,
  regardless of timestamp.
- Missing or malformed container-start or job-creation timestamps fail closed.
- All other existing active statuses, unknown-state behavior, V1/V2/Lab checks,
  and planning-operation checks remain unchanged.

The activation workflow captures the running V3 container ID and start time
before its first inventory. It passes that same start time to the pre-maintenance
and post-fence inventories and verifies the stopped container is still the same
container. This makes the comparison stable across the drain and does not infer
activity from file mtime.

## Scope

This changes only the deployment guard's interpretation of old, unclaimed,
non-project V3 `planned` records. It does not mutate, delete, fail, or migrate
those records; does not weaken protection for project-executor queue entries,
executing jobs, or jobs created during the current container lifetime; and does
not change generation behavior. A request waiting in the generic synchronous
route before it changes a `planned` job to `generating` may receive a cutover
connection error; no provider call has started and the unchanged durable plan
remains available for retry after the deployment.

## Acceptance

1. Old non-project `planned` record without execution marker is reported as
   preserved and does not block cutover.
2. Current-lifetime `planned` record blocks cutover.
3. Old `planned` record with a background attempt marker blocks cutover.
4. Old project-associated `planned` record remains blocking because project
   generation may still be in the in-memory executor queue.
5. Missing/malformed timestamps fail closed.
6. `queued`, `generating`, and `finalizing` continue to block.
7. Workflow captures a single container identity/start time and reuses it for
   both inventory checks; identity drift blocks before backup or activation.
8. Existing V1/V2/Lab, storage-root, backup, rollback, and public-health
   safeguards remain intact.
9. Focused tests and GitHub CI pass; an independent review examines the exact
   merged candidate before another guarded VPS activation attempt.

## Deployment boundary

The prior activation stopped before maintenance and left the active release,
V1/V2 services, maintenance timer, and public health unchanged. Any subsequent
attempt must use a newly prepared candidate for the merged SHA, rerun the
read-only preflight, and keep the existing 1 GiB free-space reserve. If any
active-work, disk, root, backup, or health guard fails, do not bypass it.
