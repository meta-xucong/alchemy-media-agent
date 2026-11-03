# Bridge Codex timeout projection

## Correction model

Bridge is authoritative for the Codex turn boundary: after at most 600 seconds
it terminates the local app-server process and reports
`codex_turn_timed_out`. The result may still be unknown upstream, so the same
Bridge attempt remains held for reconciliation. The product job must end in a
visible terminal error so its UI does not wait forever, while the Bridge slot
stays held until same-attempt reconciliation. Alchemy must show that timeout
without changing the existing no-duplicate rule.

The previous projection lost this information: `action_required_detail` was
filtered by Alchemy's curated attention map, and the V3 outer call could expire
before Bridge's 600-second Codex timeout. Users therefore saw a generic wait
state even though Bridge had stopped its local session.

## Minimal correction

1. Add the Bridge timeout and overdue-reconciliation codes to Alchemy's curated
   message map. Do not forward arbitrary Bridge text.
2. Carry only the allowlisted reason code through the existing primary
   transport projection. V1/Lab, V2 and V3 use their existing status surfaces
   to show the same-task reconciliation message.
3. When V3 Bridge is enabled, give its outer provider call and poll budget
   enough time to receive and persist Bridge's timeout result.
4. Keep `execution_unknown` bound to the original Bridge task. Do not release
   its slot, start a second renderer, or invoke API fallback from this timeout.
5. Mark the Alchemy V1/Lab and V2 product job terminal-failed for the explicit
   timeout and overdue-reconciliation codes. Keep the Bridge execution ledger
   and slot in attention until evidence resolves the original attempt.

## Acceptance

- A timeout reason reaches desktop/mobile V1, Lab, V2 and V3 through curated
  text; arbitrary remote message text is not exposed.
- V1/Lab and V2 stop presenting the product job as actively generating after
  the Bridge timeout; the Bridge physical slot remains held for reconciliation.
- V3 outer and polling budgets cover the Bridge timeout.
- A timed-out unknown execution stays on the original Bridge route and does
  not invoke the API provider.
