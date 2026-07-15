# E21: E-Commerce Provider-Independent Code-Closure Record

Status: `code_closure_passed` for the Alchemy-owned E-Commerce template/UI
work package in Doc132 §5. This is not a Provider, pixel-review, Gate C, Gate
D, or production-release result.

## Scope and Boundary

This record covers only the E-Commerce forward path on the frozen mainline
baseline `origin/main@d521b3777654edfe7c0d92cc15d5371e509bdde3`:

```text
factual product/platform context
-> remote-Brain-shaped deterministic fixture
-> exact frozen whole-image directions
-> shared deterministic generation/result projection
-> Project Mode aggregation, refresh/reopen, and append-only continuation
```

It does not invoke an upstream image Provider, render E-Commerce through Local
MCP, create a local renderer, alter shared Provider/review/retry ownership, or
enable a production flag.

## Verified Fixture Contract

`test_v3_doc132_ecommerce_code_closure.py` uses the existing shared
`V3ProductApiService` / `V3ProductRouteHandlers` deterministic generation and
result-projection seam with the explicit remote-Brain contract test provider.
It proves:

1. requested counts `1`, `2`, `4`, and `7` each produce the same count of
   Brain-authored natural-language intents, opaque output identities,
   candidates, and ordinary Project Mode results;
2. new E-Commerce jobs have no selected/default executable mode or preset;
   legacy `marketplace_listing_set` input is auditable as ignored and never
   reaches the Brain request, provider prompt, delivery projection, or browser
   surface;
3. the only continuation identity is opaque (`ecommerce_output_N`); a child is
   append-only and can become the current delivery without overwriting parent
   history;
4. a malformed remote-Brain response is fail-closed with no ordinary project
   delivery, and a shared held/manual-confirmation outcome is not presented as
   a final result; and
5. the browser source describes LLM-created whole-image directions and has no
   fixed main/selling/scene/trust-image promise or executable E-Commerce
   preset.

Historical identifiers remain accepted by compatibility readers. They are
explicitly removed from every new E-Commerce runtime selection before the
Brain/envelope/materialization path.

## Deferred Local MCP Visual Recheck: Frozen Specialized-Plan Relay

Local MCP visual comparison is not a Provider dependency and must not delay
the code-closure verdict above. The current MCP entry is intentionally
General-only, so it cannot render this E-Commerce job without a mainline-owned
relay. When that relay is added, the smallest safe consumable contract is:

```text
frozen template_id/scenario_id = ecommerce_template/ecommerce
+ opaque output identity and ordinal within requested count N
+ frozen remote-Brain binding and exact-N direction hash
+ canonical final Provider prompt hash
+ declared/admitted reference count and source hashes
-> one Codex built-in ImageGen call for that exact frozen output
-> conversation_only_not_certified
```

The relay must reject a missing/mismatched frozen binding, direction hash,
prompt hash, reference admission, template, or ordinal. It must not replan,
rename the work as General, introduce a local recipe, create a candidate,
write project delivery/history, invoke review/retry, or produce Gate C/D
evidence.

The mainline test recommendation is one relay-contract fixture that proves
exact `N=1,2,4,7` calls, byte-identical canonical prompt/reference hashes for
each opaque output, refusal on every mismatch, and no Project Mode persistence.
That future MCP result is a visual-direction comparison only; it remains
separate from both this `code_closure_passed` record and
`production_gate_pending`.

## Closure Labels

| Label | Result | Meaning |
| --- | --- | --- |
| `code_closure_passed` | yes | The applicable E-Commerce fixture, lifecycle, projection, and UI contracts are green. |
| `code_defect` | no | No reproducible E-Commerce code defect remains in this Doc132 work package. |
| `upstream_hold` | yes | Web `image_edit` admission remains externally blocked by the payload-safe `image_edit_invalid_request_unattributed` diagnosis. |
| `production_gate_pending` | yes | Doc127 real Provider pixels, certifying review, restricted provenance, and human sign-off remain outstanding. |

## Exclusions

No customer media, full prompts, credentials, endpoint/account details, raw
Provider responses, generated media, or MCP-rendered E-Commerce output is
included in this record. The existing E19 real-Provider record remains the
authority for the upstream hold and is not changed by this code-closure result.
