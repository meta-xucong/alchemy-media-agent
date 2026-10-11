# V1/Lab image publication security

## Correction model and scope

The previous generation path wrote original, thumbnail and preview bytes before
the canonical Output/Job transaction. Billing could await after those writes.
An inventory build or filesystem-recovery read could therefore classify a new
private output as ownerless legacy-public. This is a persistence/publication
defect, not a reason to infer output ownership from the Session.

The minimal correction is durable, immutable per-output reservation authority
before bytes, plus one shared fail-closed publication predicate. Canonical Output
ownership remains the publication authority. History, known/unknown direct-ID
lookup, media responses and V1 anonymous local share rendering use that boundary.
This work does not call Providers, perform billing, modify user data, deploy, or
establish production security acceptance.

The independent review identified additional local read bypasses in the same
visibility boundary. Their defensive corrections are included below. Final
independent security review is incomplete; passing these focused synthetic
regressions is not a security sign-off or authorization to deploy.

## Publication states

1. `LocalMediaStore.save_base64_output` commits a `v1_records` record in namespace
   `output_publications`, keyed by output ID, before creating original bytes.
   Its payload has the intended Job ID and owner supplied explicitly by
   `ImageGenerationRequest.veyra_user_id`. No Session owner is consulted.
2. Every reservation is single-use. Existing reservations, including identical
   pending reservations and reservations retained after deletion, are rejected.
   Existing canonical output IDs cannot be materialized again. Existing service
   retries mint fresh output IDs; there is no new same-ID recovery workflow.
3. Original, thumbnail and preview files may now be written. They remain hidden
   from every reader until a matching canonical Output commits. The exact output
   ID, Job ID and normalized explicit owner must match the reservation.
4. The existing `repository.save_job` transaction persists canonical Output and
   nested Job outputs after generation/postprocessing/billing succeed. Normal
   history ownership precedence then applies. A deliberately ownerless request
   can become public only after its matching ownerless Output commits.
5. Cancellation, process interruption, write failure, failed billing, absent
   canonical records and owner/Job mismatches leave the reservation blocked.
   Neither a manifest nor a nested copy can override a managed reservation.

Reservations are security evidence, not disposable derived index state. Index
rebuilds and ordinary output deletion retain them. This uses one small durable
row per attempted managed output, including failed attempts; disk use grows with
attempt count. Automatic reservation garbage collection and ID/owner transfer
are intentionally unsupported because removing this fence can reopen recovery.

## Legacy classification and migration

No existing files are relabeled or backfilled, and no ownership is synthesized.

| Unmarked existing record | Classification |
| --- | --- |
| Canonical Output, manifest, or nested Job output evidence | Existing published legacy record; existing per-output ownership/conflict rules apply |
| Bare filesystem file with a known parent Job, absent published output evidence | Pending/unknown; exclude from history and deny media reads |
| Bare filesystem file with no known Job and no publication reservation | Genuine orphan recovery; preserve legacy-public behavior |

The second row is a deliberate compatibility narrowing: uncertain interrupted
generation bytes under known Jobs are no longer automatically public. Operators
must investigate and restore actual per-output authority if recovery is desired;
the application does not assign the Session owner's identity or manufacture a
public grant. Removing a Job can change an unmarked historical file's
classification, so Job changes queue all corresponding file-only output IDs.
Managed reservations remain blocked even if their Job is later removed.
Destroying canonical records with `repository.reset()` is not equivalent to
restarting the application: a remaining manifest cannot republish a managed ID
after that destructive reset. Real process restart retains canonical authority.

## Read paths and authority refresh

- V1 history and Lab history call the same publication predicate before inserting
  winners/counts. Publication namespace changes are tracked transactionally.
- Canonical Output updates dirty the affected ID; global/session/owner counts are
  refreshed before a clean indexed page can be returned. No private pending ID
  is counted as public, including during initial explicit inventory preparation.
- `/v1/outputs/{id}/download`, `/thumbnail` and `/preview` all deny unpublished
  bytes. This is also enforced with authentication disabled. The lower-level
  file resolver repeats the check so internal local-file readers cannot skip it.
  Direct IDs reject glob syntax, separators, NUL and dot traversal, while keeping
  irregular literal legacy IDs. Fallback candidates must match the requested ID,
  remain inside generated storage, and pass publication checks using their actual
  parent Job even when added after the prepared inventory. Unmarked legacy MP4
  lookup is unchanged by the image-only pending-file classification.
- Favorite/revision entry points use the shared read guard. Lab generation
  delegates to the same image generation/storage path and uses these same media
  URLs; no separate Lab binary publication path exists.
- Anonymous V1 share rendering has no durable public share grant. Private,
  conflicting or unpublished V1/Lab media cannot be rendered into a public share
  image. `/share/save-image` checks before cached-file access and returns 404 for
  blocked media. Poster/source-image loading retains its existing safe public
  placeholder. Both absolute and relative V1 URLs are classified.
- Existing private share cache files are neither deleted nor overwritten; the
  route refuses to serve them. Guarded renditions use a new cache namespace instead
  of trusting older entries. Nested `/share/*` documents are rejected as image
  inputs; the shipped frontend passes direct media URLs. This avoids indirect
  cached renditions bypassing current media authority.
- Static and mobile-static share sources must resolve inside their fixed public
  roots. The same check applies before cached-file access, including encoded
  traversal and symlink containment.
- Protected V1 media and share-image/poster responses now use `private, no-store`.
  Old publicly cached browser/CDN bytes and already downloaded public data cannot
  be retroactively revoked. No cache purge or production-data operation was run.

## V2 share adapter boundary

The V1 share renderer previously opened V2 output/thumbnail files directly from
the V2 storage directory. A file path is not a V2 publication grant. That shortcut
is removed without importing any V2 storage, database or ownership logic into V1.

For a V2 media URL, the renderer requests the existing V2 media endpoint using the
configured `_v2_proxy_target_url`, never the supplied URL's origin or the caller's
Host. It forwards no bearer token or cookie and follows no redirects. Retrieval
has an eight-second transport timeout/deadline check and a 32 MiB content cap.
Successful anonymous media bytes are rendered; denied, missing, offline,
redirected or over-budget responses produce the existing public placeholder.

Every V2 share-image response renders request-local checked bytes; it never trusts
or mutates an existing shared cache rendition. Public V2 sharing remains possible
when V2's own endpoint permits anonymous access. A local V2 file alone is no
longer sufficient, and private/offline V2 previews may now show the placeholder.
This intentionally changes the old local-file smoke contract. V2 publication
internals and V3 sharing remain outside this correction.

## Deletion retry boundary

A partially completed delete can remove canonical Output authority before its
durable delete claim is finalized. The retained publication reservation must
continue blocking list/download/share access, but must not prevent cleanup.
Only the deletion endpoint can use an existing delete claim to authorize the
same owner (or existing admin/local unauthenticated mode) to retry cleanup.
Another account cannot use it, and no read route accepts this exception.

## Empty-store preparation interaction

Read requests no longer perform cold history import/build. A native first
`save_history_record` exclusively creates an empty JSONL source if none exists,
then runs the existing strict importer to establish an actual zero-record
receipt before its native append. An existing source is never overwritten or
declared imported without validation. This lets a prepared empty store remain
incrementally readable after its first generated history record, while an
unknown restored legacy source still requires explicit maintenance preparation.

## Synthetic verification

`tests/test_v1_image_publication_security.py` covers reservation-before-file,
file-before-canonical, warm readers and inventory during a paused writer,
owner/Job mismatch, missing canonical, failed-billing-style cleanup, single-use
ID retry rejection, explicit owner propagation, ownerless legacy compatibility,
known-Job unknown-file classification, V1/Lab owner/surface counts, three media
endpoints for owner/other account, auth-disabled denial, deletion-claim retry,
and anonymous share cache/source bypasses. Tests use only temporary storage and
synthetic images with network connections forbidden by the validation runner.
Additional regressions cover stale dirty Job sources, literal direct IDs, unknown
file parent revalidation, share wrappers/public-root containment, HTTP no-store,
and mocked V2 public/denied/redirected media responses without real network calls.

Final focused command (isolated temporary-storage, socket-denying runner):

```sh
/workspace/shared/media-history-v1-venv/bin/python /tmp/media_history_pytest.py v1 \
  tests/test_v1_image_publication_security.py tests/test_v1_history_strict_import.py \
  tests/test_v1_history_delete_atomicity.py tests/test_api_smoke.py \
  -k 'publication or history_delete or history_strict or image_share or managed_image_history_fails_closed'
```

Result: **149 passed, 91 deselected**. This is a focused receipt, not the complete
repository suite; aggregate validation is recorded separately by integration.
