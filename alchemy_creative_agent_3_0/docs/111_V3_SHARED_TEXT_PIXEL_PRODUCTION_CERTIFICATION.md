# 111 V3 Shared Text-Pixel Production Certification

Status: certification infrastructure is implemented; production delivery is
not certified and remains disabled by default.

## Scope

This document extends Doc107 and Doc110. It governs only shared deployment
inputs, final-pixel OCR readiness, release evidence, and production gates. It
does not add any template role, marketplace policy, public font/OCR control,
Provider route, General Template behavior, or retry semantic.

## Production font manifest

Deployment supplies `V3_TEXT_PIXEL_FONT_MANIFEST_PATH`, a versioned JSON
manifest conforming to:

```text
deployment/text_pixel/production_font_manifest.schema.json
```

Every entry requires a font ID, version, file path, license ID, license-evidence
reference, SHA-256, supported locales, and `production_approved=true`. The
shared resolver records manifest provenance and returns structured failures for
missing files, missing evidence, missing hashes, hash mismatch, unsupported
locale, missing glyphs, and non-approved fonts. It never silently substitutes
a font, language, or character.

The intended first-release locale matrix is:

| Locale | Required deployment proof |
| --- | --- |
| `en-US` | Latin glyph probe and publishable font evidence |
| `zh-CN` | Simplified Chinese glyph probe and publishable font evidence |
| `ru-RU` | Cyrillic glyph probe and publishable font evidence |

No font binary or license claim is bundled in this repository. Asset owners
must place approved fonts in the deployment and retain their license evidence.

## OCR preflight

`TesseractOcrEngine.preflight()` creates a harmless final-raster probe per
locale and reports one of:

```text
ocr_binary_unavailable
ocr_language_data_unavailable
ocr_invocation_failed
ocr_final_pixel_success
```

The shared review continues to invoke OCR against actual post-composition
pixels. Missing OCR blocks both required-text and text-forbidden deliveries;
the latter may not pass merely because no overlay was planned.

## Certification record and flags

The runtime accepts a deployment-owned
`V3_TEXT_PIXEL_PRODUCTION_CERTIFICATION_JSON` record only when it has a
version, matches the active font-manifest version, records passed OCR preflight,
passed Gate C, passed Gate D, and non-empty retained evidence references.

The default flags are unchanged:

```text
V3_TEXT_PIXEL_DELIVERY_ENABLED=false
V3_TEXT_PIXEL_DELIVERY_PRODUCTION_ENABLED=false
V3_TEXT_PIXEL_ALLOW_DEVELOPMENT_FONTS=false
```

If a deployment sets the production flag without a complete matching
certification record, the shared runtime returns
`production_certification_incomplete`. The flag does not bypass font/OCR
validation. The `production_preflight()` report is diagnostic only; it never
turns a flag on.

## Gate C/D evidence still required

Production certification is blocked until asset-owner-approved real Provider
runs retain source consent, product facts, approved copy/claim decisions,
font/OCR/flag provenance, provider and append-only derived outputs, review
records, human visual acceptance, and terminal Gate C/D decisions. The minimum
matrix remains text-forbidden, `en-US`, `ru-RU`, `zh-CN`, and bounded provider
failure/retry coverage.

Until that record exists, all consumers must keep `planned_only`, blocked, and
correction results visibly non-production.
