# V3 repaired release deployment: capacity correction

The requested outcome is deployment of the repaired V3 code so the user can
perform frontend generation. Live generation acceptance remains with the user.

Candidate build `42463297143` prepared `93fd790f`. Activation `42463727970`
found no active work both before and after fencing. Its two explicitly named
historical V2/API unknown units passed the existing failed/empty-output checks.
The run stopped at `consistent_store_backup_failed` before store backup or
index mutation, then verified rollback to `75e5827c`.

## Correction model before implementation

- Intended: retain the 1 GiB reserve, back up durable stores and activate the
  candidate. Observed: candidate construction consumed about 981 MB, leaving
  1,617,498,112 bytes, below the 1,907,880,470-byte data requirement reported by
  read-only preflight `42463971879`. Backup itself needs another 346,144,367
  estimated bytes; the post-backup capacity check must also pass.
- Owning layer: deployment resource capacity, auxiliary to V3 planning and
  generation. No Brain, provider, routing or quality rule needs changing.
- Authority: existing backup and post-backup capacity guards stay unchanged.
  The earlier pre-build capacity snapshot cannot establish post-build capacity.
- Minimal repair: an opt-in input on the existing locked candidate workflow
  removes only explicitly selected unused `alchemy-media-agent:candidate-*`
  Docker image tags. Validate the complete selection before deletion, matching
  revision labels and rejecting the new target, current/rollback image IDs,
  container-used images and additional tag aliases. Use Docker removal without
  force. Keep source worktrees, databases, outputs and all backups untouched.
- Verify exact scoped removal and refusal cases with mocked Docker. Then build
  the integrated revision, check post-build capacity, and run the unchanged
  guarded activation with the 1 GiB reserve. No provider generation is part of
  this deployment task.

The observed unused candidate revisions selected for retirement are
`76c993116791cd68d3753d00a390a919d67ae67e`,
`371eea428649363428bf826b996e6feeeaa21915`,
`c01bf21a02c506fb3317c400ca28e5bf96ab607a`, and
`93fd790faac679889855c2e1273fe741807fc79b`. Their source releases remain available
for rebuilding. Active `75e5827c` and rollback `cb89ec1a` are preserved.

## Verification before deployment

The new helper's 11 mocked-Docker tests pass, including full-selection
validation before removal, exact non-force commands, and protected/in-use,
revision and alias rejection. The related release contract/runtime test set
has 45 passing tests in total. Two existing Bash execution fixtures fail on
this Windows host (the system Bash launcher produces non-UTF-8 output); the
unchanged runtime install functions will also execute in the real Linux
candidate workflow. Workflow YAML parsing, explicit Git Bash syntax checks
and `git diff --check` pass. A read-only scope monitor reviewed the actual
helper, wiring and correction model without finding a scope violation.

Production remains on the verified rollback until the new integrated
candidate passes build, post-build capacity assessment and guarded activation.
