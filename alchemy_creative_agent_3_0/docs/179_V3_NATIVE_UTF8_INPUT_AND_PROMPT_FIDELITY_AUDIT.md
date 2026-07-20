# Doc179 — V3 Native UTF-8 Input and Prompt Fidelity Audit

## Decision

V3 treats user text as Unicode from the browser boundary through Product API,
job persistence, Remote Brain payloads, canonical Provider prompt materialization,
review metadata, and local MCP relay output. No ASCII-only conversion or local
translation layer is allowed to rewrite the user's language.

## Runtime contract

- Browser requests use `JSON.stringify` with `Content-Type: application/json`.
- FastAPI reads the request body as JSON and preserves Unicode values.
- V3 JSON persistence uses UTF-8 and `ensure_ascii=False`.
- Remote Brain payloads and canonical prompt hashes are computed from UTF-8 bytes.
- Native MCP stdio explicitly configures UTF-8 input and output.
- Image bytes remain base64 transport data; this does not change text encoding.

## Failure boundary

Replacement characters or question-mark corruption introduced by an external
shell, console, or test harness are not valid V3 input. Test runners must send
JSON through an HTTP client or a UTF-8 file/stream, never through a code page
dependent console pipeline. V3 must not silently repair corrupted user intent.

## Acceptance evidence

The regression contract covers:

1. Chinese project and visual-asset text through the real FastAPI JSON boundary;
2. Chinese user intent in the Remote Brain payload and UTF-8 byte representation;
3. Chinese display name and preparation intent after catalog persistence/reopen;
4. unchanged prompt ownership and no local prompt reconstruction.

This audit does not add language-specific prompt recipes or keyword rules.
Chinese is a transport and fidelity concern; creative interpretation remains
owned by the Remote Brain and the existing shared runtime.
