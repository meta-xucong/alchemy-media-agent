# Image generation timeout alignment amendment

## Scope and evidence

Three Sub2API records for `gpt-image-2` show HTTP 400 `image_poll_timeout`
responses from the upstream `404token-unified-openai` account after 140–146
seconds. The account endpoint is `404token.xyz`; Sub2API recorded the failures
as upstream responses, not connection or client timeout errors. The account's
Sub2API metadata exposes no per-account polling timeout.

The Alchemy V2 image client previously defaulted to 240 seconds. Alchemy's
public Nginx configuration also had a 300-second proxy wait. The failure is
owned by the configured `404token.xyz` upstream and is independent of other
providers that are no longer in service.

## Correction model

- Set Alchemy V1/LAB and V2 image request defaults to 600 seconds.
- Set Alchemy Nginx proxy read/send waits to 720 seconds so the client-facing
  proxy does not close the request before the application deadline.
- Keep the existing 600-second local V1/LAB request setting and 900-second
  high-resolution/queue budgets.
- The 404token service's 140-second response is generated upstream. Increasing
  Alchemy or Sub2API wait limits cannot override that service's own deadline;
  that requires a 404token-side configuration or a provider change. An
  administrator API key has been supplied, but its management endpoint still
  needs to be identified before using it.

## Acceptance

- Focused Alchemy configuration tests require at least 300 seconds.
- Validate the Nginx configuration before reload and restart only the Alchemy
  V2 API after changing its environment.
- Do not use real image generation as a timeout probe. Verify deployed settings
  and preserve existing upstream timeout records.
