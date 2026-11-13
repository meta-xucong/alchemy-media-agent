# RB35 — Admin-Verified Node Reward Binding Correction

Date: 2026-11-14
Status: implementation target for this isolated feature branch; not published or deployed.

## Problem and owner

Alchemy owns the account-to-node reward binding. The current user endpoint
accepts a unique node ID after Alchemy login, but the ID is not proof that the
requesting account controls the node. The existing API correctly rejects a
second account, but it has no supported way to correct an accidental binding.
Deleting the row would also erase the previous account's visible accrued total.

This correction belongs in Alchemy's node-reward persistence and protected
administrator surface. RenderBridge remains the source of cumulative real
image counts; Alchemy remains the source of account ownership. Do not add a
public self-unbind or transfer endpoint.

## Correction model

Only an authenticated Alchemy administrator may move an exact
`(pool_id, node_id, executor_instance)` binding to another active Alchemy
account. The operation is a direct transfer in one SQLite transaction; it
never creates an unowned interval that another account can claim.

The request carries the current owner and monotonically increasing binding
revision observed by the administrator. Before writing, the backend reads a
complete Bridge reward snapshot and validates the exact node tuple and its
nonnegative `rewardable_images` count. The transaction then:

1. compares the active row's owner and revision with the request;
2. rejects a missing, stale, or regressed metric without modifying data;
3. freezes the old account's accrued images as
   `observed_count - old_baseline` in an append-only history row;
4. sets the new owner's baseline to the same observed count and increments the
   binding revision.

The image-count snapshot is the transfer boundary. Since Bridge exposes a
cumulative count rather than per-image ownership timestamps, a receipt that
commits after the snapshot belongs to the new account. This limitation is
displayed in the admin correction confirmation.

The old account continues to see its frozen images and calculated points. The
new account starts at zero and accrues only after the transfer boundary. The
administrator's lifetime totals include both closed and active ownership
periods. Points remain reporting-only at `0.02` per rewardable image; this
operation does not create spendable balance or payout records.

## API and UI

Add a same-origin-guarded administrator write route under
`/v1/admin/render-bridge/rewards`, protected by the existing RenderBridge
administrator resolver. The body contains the exact node tuple, expected
`user_id`, expected binding revision, and destination active `user_id`.
Reject malformed identities, inactive or missing destination accounts,
truncated Bridge metrics, missing tuple, missing baseline, stale revision, and
counter regression. Return only a bounded status and updated revision.

The existing admin node card exposes the current account ID and a collapsed
“修正账号归属” form. It requires a destination account ID and confirms that
the current counter is the ownership boundary. The ordinary account page has
no unbind or transfer control. It displays corrected historical periods as
read-only reward history.

## Persistence

- Add a monotonic `binding_revision` to active bindings, defaulting to 1 for
  existing rows.
- Add append-only closed binding periods with the exact tuple, former account,
  start/end timestamps, baseline, and finalized image count. Do not store task
  IDs, prompts, media, or Bridge credentials.
- Keep the existing active binding primary key and unique-node ownership
  constraint. Update the account row and insert history under one
  `BEGIN IMMEDIATE` transaction.
- Derive points from image counts with the existing shared `Decimal` rate;
  do not store a second mutable points counter.

## Acceptance tests

1. Admin authentication and same-origin checks guard the correction route.
2. A complete exact Bridge snapshot and active destination account are
   required; truncated, missing, or regressed metrics leave both tables
   unchanged.
3. With old baseline 3, observed count 6, and later count 8, the old account
   retains 3 images / 0.06 points, the new account sees 2 images / 0.04
   points, and the administrator's lifetime aggregate is 5 images / 0.10
   points.
4. A repeated request or an action with an old revision receives a conflict
   and creates no duplicate history row.
5. A plain account cannot transfer or release the node; knowing the node ID
   alone does not create an ownership proof.
6. Existing first-bind baseline behavior and the normal node rewards page
   remain unchanged.

This feature is implementation-ready after the above tests, an independent
review of authorization and transaction boundaries, and Alchemy's focused
admin/account UI regression suite pass. It is not live accepted until a
separately authorized release shows the corrected account totals on the
deployed version.
